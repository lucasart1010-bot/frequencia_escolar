# 📋 Frequência Escolar — Data Mart de frequência

Sistema web (Streamlit + Supabase) para lançar a chamada da turma **5º Ano B (Tarde)** durante 15 dias
e gerar um dashboard de risco de evasão. Funciona em celular e PC.

## Estrutura
```
app.py             # interface (Chamada, Dashboard, Alunos) + acesso ao banco
analise.py         # regras de risco (pandas puro)
importar.py        # lê nome e contato da planilha de alunos (.xlsx/.csv)
dados/alunos_5_ano_B_tarde_2026.xlsx   # lista da turma (29 alunos, dados fictícios)
schema.sql         # 2 tabelas: alunos e frequencias
seed_alunos.sql    # carga inicial dos 29 alunos (nome e contato) no Supabase
frequencia_escolar.html  # versão independente: 1 arquivo, sem Python (abrir no navegador ou hospedar)
previa_frequencia.html   # pré-visualização estática (só para ver o visual)
requirements.txt
.streamlit/secrets.toml.example
```

## Rodar local (modo demonstração, sem banco)
```bash
pip install -r requirements.txt
streamlit run app.py
```
A lista de alunos vem da planilha em `dados/`. Na aba Dashboard, **Gerar 15 dias de exemplo** cria
presenças fictícias para mostrar os gráficos.

## Ligar ao Supabase
1. Crie um projeto em supabase.com e rode `schema.sql` e depois `seed_alunos.sql` no SQL Editor
   (ou, com o app já ligado, use **Alunos > Importar lista da turma**).
2. Copie `.streamlit/secrets.toml.example` para `.streamlit/secrets.toml` e preencha URL e chave `service_role`.
3. Rode de novo: o app muda para **Supabase** sozinho.

## Alunos
- **Entrou no meio do ano:** aba Chamada > ➕ Adicionar aluno (aparece só nas datas a partir da entrada).
- **Lista nova da turma:** aba Alunos > Importar (.xlsx ou .csv com as colunas "NOME DO ALUNO" e "CONTATO").
  Nome e contato são lidos; a data de nascimento é ignorada de propósito.

## Número de contato
- Aparece no cartão da chamada, no alerta vermelho de risco e na tabela do dashboard (também no CSV baixado).
- Quando o número tem DDD + 8 ou 9 dígitos, o app mostra um link do WhatsApp (https://wa.me/55...).
- Números fora do padrão ficam marcados com ⚠️ para a professora conferir. Na planilha enviada: Ana Gabriela
  (9 dígitos) e Esther Gabrielly (12 dígitos).
- Se a tabela `alunos` já existia no Supabase sem o contato: `alter table alunos add column if not exists contato text;`

## Hospedar (grátis)
1. Suba a pasta no GitHub (o `secrets.toml` fica de fora pelo `.gitignore`).
2. share.streamlit.io → New app → escolha o repositório e `app.py`.
3. Em **Settings > Secrets**, cole o conteúdo do `secrets.toml`.

## Regras do dashboard
- **Risco de evasão:** 3 faltas seguidas **ou** 30% de faltas no período (editável na tela).
- Por padrão só "Falta" conta; justificadas entram marcando a opção.
- **Referência pública:** LDB (Lei 9.394/1996) art. 24, VI — frequência mínima de 75%;
  art. 12, VIII (Lei 13.803/2019) — escola notifica o Conselho Tutelar quando as faltas passam de
  30% do percentual permitido em lei (30% de 25% = 7,5% dos dias letivos).

## Dados de alunos = dados pessoais (LGPD)
A planilha de exemplo é fictícia. Com dados reais, use a senha de acesso (`[app] senha`) e a chave
`service_role` só nos secrets.

## Versão independente (frequencia_escolar.html)
Funciona sem Python e sem banco: dê dois cliques para abrir, ou hospede o arquivo em qualquer site estático
(GitHub Pages, Netlify, Cloudflare Pages). Tem chamada, adicionar aluno, dashboard, importar CSV e backup.
Os dados ficam no navegador de cada aparelho; para levar de um aparelho para outro, use Exportar/Importar backup.
Se vários aparelhos precisarem enxergar os mesmos dados, use a versão Streamlit + Supabase.
Também mostra o contato dos alunos (cartão da chamada, alerta de risco, tabela e CSV), com link do WhatsApp quando o número é válido. Dados salvos antes desta atualização ganham o contato automaticamente pelo nome.
