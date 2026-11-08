# -*- coding: utf-8 -*-
# Grok Assistente para Alexa: conversa com a API da Groq, mantém o contexto da sessão,
# responde hora e data localmente e envia respostas longas para o cartão do app Alexa.
import json
import logging
import re
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

import ask_sdk_core.utils as ask_utils
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler, AbstractExceptionHandler
from ask_sdk_model.ui import SimpleCard

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ===== CONFIGURAÇÃO =====
API_KEY = "COLE_SUA_CHAVE_GROQ_AQUI"   # mantenha as aspas
API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-120b"
NOME_USUARIO = ""                      # seu nome, se quiser que a skill use (deixe vazio para não usar)
PERSONALIDADE = "direto"               # opções: "direto", "bem-humorado", "formal"
TIMEOUT_S = 5.0                        # a Alexa desiste por volta de 8 s
MAX_TOKENS_CURTO = 150                 # respostas normais, pensadas para voz
MAX_TOKENS_LONGO = 400                 # quando você pede detalhes
MAX_TURNOS = 2                         # pares pergunta/resposta guardados na sessão
MAX_CHARS_HIST = 400                   # corta respostas antigas no histórico
FUSO = timezone(timedelta(hours=-3))   # horário de Brasília (sem horário de verão desde 2019)
# ========================

PERSONALIDADES = {
      "direto": "Seja objetivo e simpático.",
      "bem-humorado": "Seja leve e bem-humorado, sem exagerar.",
      "formal": "Seja formal e cuidadoso no tom.",
}

DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
                "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
                  "agosto", "setembro", "outubro", "novembro", "dezembro"]

PALAVRAS_DE_SAIDA = {"não", "nao", "não obrigado", "nao obrigado", "nada", "tchau", "sair", "chega"}
ERRO_PADRAO = "Não consegui falar com o Grok agora. Tente de novo em instantes."


def montar_system(modo_longo):
      limite = "no máximo seis frases" if modo_longo else "no máximo duas frases curtas"
      trato = (f"O nome do usuário é {NOME_USUARIO}; use o nome de vez em quando, sem exagerar. "
               if NOME_USUARIO else "")
      return (
          "Você é o Grok, um assistente de voz em português do Brasil. "
          + trato
          + f"{PERSONALIDADES.get(PERSONALIDADE, PERSONALIDADES['direto'])} "
          f"Responda em {limite}, sem markdown, listas, emojis ou símbolos. "
          "Escreva números e siglas por extenso quando fizer sentido, pois a resposta será falada. "
          "Se a pergunta for continuação da conversa, use o contexto anterior."
      )


def limpar_fala(texto):
      """Remove marcações e caracteres que a Alexa não deve ler em voz alta."""
      texto = re.sub(r"[*#`_]", "", texto)
      texto = re.sub(r"(?m)^\s*[-•]\s*", "", texto)
      texto = texto.replace("&", " e ").replace("<", " ").replace(">", " ")
      texto = re.sub(r"\s+", " ", texto).strip()
      return texto[:3000] or "Não encontrei uma resposta para isso."


def primeiras_frases(texto, n=2):
      partes = re.split(r"(?<=[.!?])\s+", texto)
      return " ".join(partes[:n])


def responder_hora_data(texto):
      """Responde hora e data localmente, sem chamar a API."""
      t = texto.lower()
      agora = datetime.now(FUSO)
      if re.search(r"\b(que horas|horas são|hora é|hora agora|que hora)\b", t):
                h, m = agora.hour, agora.minute
                verbo = "é" if h == 1 else "são"
                hora_txt = "uma hora" if h == 1 else f"{h} horas"
                minutos = f" e {m} minuto{'s' if m != 1 else ''}" if m else ""
                return f"Agora {verbo} {hora_txt}{minutos}."
            if re.search(r"\b(que dia|qual é a data|qual a data|data de hoje|dia é hoje|que data)\b", t):
                      return f"Hoje é {DIAS[agora.weekday()]}, {agora.day} de {MESES[agora.month - 1]} de {agora.year}."
                  return None


def _chamar_api(messages, max_tokens):
      payload = {
          "model": MODEL,
          "max_tokens": max_tokens,
          "messages": messages,
          "reasoning_effort": "low",
}
    for _ in range(2):
              req = urllib.request.Request(
                            API_URL,
                            data=json.dumps(payload).encode("utf-8"),
                            headers={
                                              "Content-Type": "application/json",
                                              "Authorization": "Bearer " + API_KEY,
                                              "User-Agent": "alexa-grok-skill/1.0",
                            },
                            method="POST",
              )
              try:
                            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                                              data = json.loads(resp.read().decode("utf-8"))
                                          return data["choices"][0]["message"]["content"]
except urllib.error.HTTPError as e:
            # alguns modelos recusam reasoning_effort; tenta de novo sem ele
            if e.code == 400 and "reasoning_effort" in payload:
                              logger.warning("Modelo recusou reasoning_effort; tentando sem ele")
                              payload.pop("reasoning_effort")
                              continue
                          raise
    raise RuntimeError("Não foi possível obter resposta da API")


def perguntar(messages, max_tokens):
      inicio = time.time()
      try:
                return _chamar_api(messages, max_tokens)
finally:
        logger.info("Groq respondeu em %.2f s", time.time() - inicio)


def _historico(handler_input):
      return handler_input.attributes_manager.session_attributes.get("historico", [])


def _guardar(handler_input, historico):
      recentes = historico[-(MAX_TURNOS * 2):]
      handler_input.attributes_manager.session_attributes["historico"] = [
          {"role": m["role"], "content": m["content"][:MAX_CHARS_HIST]} for m in recentes
      ]


def _falar(handler_input, texto, reprompt=None):
      rb = handler_input.response_builder.speak(texto)
      if reprompt:
                rb = rb.ask(reprompt)
            return rb.response


class LaunchRequestHandler(AbstractRequestHandler):
      def can_handle(self, handler_input):
                return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
              handler_input.attributes_manager.session_attributes["historico"] = []  # conversa nova
        return _falar(handler_input, ("Oi, " + NOME_USUARIO + "!" if NOME_USUARIO else "Oi!") + " Eu sou o Grok. O que você quer saber?",
                                            reprompt="Pode fazer sua pergunta.")


class StopCancelHandler(AbstractRequestHandler):
      def can_handle(self, handler_input):
                return (ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input)
                                        or ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
              return handler_input.response_builder.speak("Até logo!").set_should_end_session(True).response


class HelpHandler(AbstractRequestHandler):
      def can_handle(self, handler_input):
                return ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
              return _falar(handler_input,
                                                  "Pode me fazer qualquer pergunta. Diga, por exemplo, que horas são, "
                                                  "ou peça detalhes que eu mando o texto completo no app.",
                                                  reprompt="O que você quer saber?")


class PerguntaHandler(AbstractRequestHandler):
      """Atende qualquer intenção personalizada, usando o texto dos slots como pergunta."""

    def can_handle(self, handler_input):
              if not ask_utils.is_request_type("IntentRequest")(handler_input):
                            return False
                        return not handler_input.request_envelope.request.intent.name.startswith("AMAZON.")

    def handle(self, handler_input):
              intent = handler_input.request_envelope.request.intent
        partes = [s.value.strip() for s in (intent.slots or {}).values()
                                    if s and s.value and s.value.strip()]
        texto = " ".join(partes).strip()

        if not texto:
                      return _falar(handler_input, "Não entendi sua pergunta. Pode repetir?",
                                                              reprompt="Qual é a sua pergunta?")

        if texto.lower().strip(" .!?") in PALAVRAS_DE_SAIDA:
                      return handler_input.response_builder.speak("Tudo bem, até a próxima!") \
                          .set_should_end_session(True).response

        resposta_local = responder_hora_data(texto)
        if resposta_local:
                      return _falar(handler_input, resposta_local, reprompt="Mais alguma dúvida?")

        t = texto.lower()
        modo_longo = bool(re.search(r"detalh|explic|resum|aprofund|passo a passo|mais informa", t))
        pede_cartao = bool(re.search(r"celular|cartão|no app|manda", t))

        historico = _historico(handler_input)
        messages = [{"role": "system", "content": montar_system(modo_longo)}] + historico
        messages.append({"role": "user", "content": texto})

        try:
                      resposta = limpar_fala(perguntar(messages, MAX_TOKENS_LONGO if modo_longo else MAX_TOKENS_CURTO))
                      _guardar(handler_input, historico + [
                          {"role": "user", "content": texto},
                          {"role": "assistant", "content": resposta},
                      ])
except Exception as e:
            logger.error("Falha na chamada à Groq: %s", e)
            return _falar(handler_input, ERRO_PADRAO, reprompt="Mais alguma dúvida?")

        rb = handler_input.response_builder
        if modo_longo or pede_cartao:
                      rb = rb.set_card(SimpleCard(title="Grok", content=resposta))
                      if modo_longo and len(re.split(r"(?<=[.!?])\s+", resposta)) > 2:
                                        falada = primeiras_frases(resposta, 2) + " Mandei o texto completo no app."
        else:
                falada = resposta
        else:
            falada = resposta

        return rb.speak(falada).ask("Mais alguma dúvida?").response


class OutrasIntencoesAmazonHandler(AbstractRequestHandler):
      """Qualquer intenção AMAZON.* não tratada acima (fallback, sim, não...)."""

    def can_handle(self, handler_input):
              return (ask_utils.is_request_type("IntentRequest")(handler_input)
                                      and handler_input.request_envelope.request.intent.name.startswith("AMAZON."))

    def handle(self, handler_input):
              return _falar(handler_input, "Não entendi. Pode repetir a pergunta?",
                                                  reprompt="Qual é a sua pergunta?")


class SessionEndedHandler(AbstractRequestHandler):
      def can_handle(self, handler_input):
                return ask_utils.is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
              return handler_input.response_builder.response


class CatchAllExceptionHandler(AbstractExceptionHandler):
      def can_handle(self, handler_input, exception):
                return True

    def handle(self, handler_input, exception):
              logger.error("Erro não tratado na skill: %s", exception, exc_info=True)
              return _falar(handler_input, "Desculpe, tive um problema. Tente novamente.",
                            reprompt="Tente de novo.")


sb = SkillBuilder()
sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(StopCancelHandler())
sb.add_request_handler(HelpHandler())
sb.add_request_handler(PerguntaHandler())
sb.add_request_handler(OutrasIntencoesAmazonHandler())
sb.add_request_handler(SessionEndedHandler())
sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()
