# Skill-Alexa-com-Grok-via-Groq-vers-o-inicial-
Skill personalizada da Alexa em português do Brasil que conversa com um modelo da Groq. Responde hora e data localmente. Envia respostas longas para o cartão do app Alexa. A chave de API não está no código: substitua COLE_SUA_CHAVE_GROQ_AQUI no console da Alexa.  Antes de confirmar, confira que o lambda_function.py do upload 
Grok Assistente para Alexa

Skill personalizada da Alexa que conversa com um modelo de linguagem pela API da Groq, em português do Brasil.

O que faz
Responde perguntas por voz, com respostas curtas pensadas para serem faladas.
Mantém o contexto das últimas trocas na mesma sessão, para perguntas de acompanhamento.
Responde hora e data localmente.
Para pedidos de detalhes, fala um resumo e envia o texto completo para o cartão do app Alexa.
Requisitos
Conta de desenvolvedor da Alexa com uma skill personalizada hospedada pela Alexa.
Chave de API da Groq (https://console.groq.com).
Configuração
Não coloque sua chave no código. No arquivo lambda_function.py, substitua COLE_SUA_CHAVE_GROQ_AQUI pela sua chave, somente no ambiente da Alexa, e nunca faça commit dela.
Se quiser que a skill use seu nome, preencha NOME_USUARIO. Deixe vazio para não usar.
Ajuste PERSONALIDADE se quiser ("direto", "bem-humorado" ou "formal").
Modelo de interação

Crie uma intenção personalizada (por exemplo, PerguntaIntent) com um slot pergunta do tipo AMAZON.SearchQuery e frases como pergunte {pergunta}, me diga {pergunta}, o que é {pergunta}. Crie também uma ConversaIntent com e {pergunta}, mas {pergunta}, e sobre {pergunta} para as perguntas seguidas.

Uso
"Alexa, iniciar grok assistente" para abrir.
"Pergunte qual é a capital da França."
Depois, sem a abertura: "e a população dela?"
"Não" ou "tchau" para encerrar.
Aviso

Este projeto não é afiliado à xAI, à Groq nem à Amazon. Os limites gratuitos da API podem mudar.
