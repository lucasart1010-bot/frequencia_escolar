"""Frequência Escolar — Data Mart de frequência (Streamlit + Supabase).

Rodar local:  streamlit run app.py
Sem credenciais do Supabase o app abre em MODO DEMONSTRAÇÃO (dados em memória).
"""
import hmac
import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from analise import STATUS_DB, distribuicao_status, resumo_por_aluno
from importar import contato_valido, formatar_contato, ler_planilha_alunos, link_whatsapp, so_digitos

# ----------------------------------------------------------------------------
# Configuração da página (responsiva: celular e PC)
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="Frequência Escolar",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .block-container {max-width: 1100px; padding: 1.2rem 0.9rem 4rem 0.9rem;}
    div[role="radiogroup"] {flex-wrap: wrap; gap: .3rem .9rem;}
    button[kind="primary"], button[kind="secondary"] {min-height: 2.8rem;}
    @media (max-width: 640px) {
        h1 {font-size: 1.6rem !important;}
        h2, h3 {font-size: 1.2rem !important;}
        .block-container {padding-left: .6rem; padding-right: .6rem;}
    }
    </style>
    """,
    unsafe_allow_html=True,
)

STATUS_UI = ["Presente", "Falta", "Falta Justificada"]
UI_PARA_DB = dict(zip(STATUS_UI, STATUS_DB))
DB_PARA_UI = {v: k for k, v in UI_PARA_DB.items()}
CORES = {"Presente": "#2E7D32", "Falta": "#C62828", "Falta Justificada": "#F9A825"}

# Lista inicial da turma (usada no modo demonstração e como exemplo de importação)
PLANILHA_PADRAO = Path(__file__).parent / "dados" / "alunos_5_ano_B_tarde_2026.xlsx"
INICIO_ANO = date(date.today().year, 1, 1)

COLS_ALUNOS = ["id", "nome", "turma", "data_entrada", "contato"]
COLS_FREQ = ["id", "aluno_id", "data", "status", "observacao"]


def texto_contato(c: str) -> str:
    """Linha de contato para cartões e alertas (com link do WhatsApp quando o número é válido)."""
    if not c:
        return "📞 sem contato"
    t = f"📞 {formatar_contato(c)}"
    link = link_whatsapp(c)
    return t + (f" · [WhatsApp]({link})" if link else " · ⚠️ conferir número")


# ----------------------------------------------------------------------------
# Acesso a dados (2 tabelas: alunos e frequencias)
# ----------------------------------------------------------------------------
def _df_alunos(linhas) -> pd.DataFrame:
    df = pd.DataFrame(linhas, columns=COLS_ALUNOS)
    df["data_entrada"] = pd.to_datetime(df["data_entrada"]).dt.date
    df["contato"] = df["contato"].fillna("").astype(str)
    return df.sort_values("nome").reset_index(drop=True)


def _df_freq(linhas) -> pd.DataFrame:
    df = pd.DataFrame(linhas, columns=COLS_FREQ)
    df["data"] = pd.to_datetime(df["data"]).dt.date
    df["observacao"] = df["observacao"].fillna("")
    return df


def _alunos_iniciais() -> list[tuple[str, str, str]]:
    """(nome, turma, contato) da planilha da turma; sem planilha, 35 alunos genéricos."""
    if PLANILHA_PADRAO.exists():
        base = ler_planilha_alunos(PLANILHA_PADRAO)
        return list(zip(base["nome"], base["turma"], base["contato"]))
    return [(f"Aluno {i + 1:02d}", "Turma A", "") for i in range(35)]


class RepoSupabase:
    """Banco real (PostgreSQL no Supabase)."""

    def __init__(self, url: str, key: str):
        from supabase import create_client

        self.sb = create_client(url, key)

    def _ler_tudo(self, tabela: str) -> list[dict]:
        # O Supabase devolve no máx. 1000 linhas por consulta -> pagina.
        dados, ini, passo = [], 0, 1000
        while True:
            r = self.sb.table(tabela).select("*").order("id").range(ini, ini + passo - 1).execute()
            dados += r.data
            if len(r.data) < passo:
                return dados
            ini += passo

    def listar_alunos(self) -> pd.DataFrame:
        return _df_alunos(self._ler_tudo("alunos"))

    def adicionar_aluno(self, nome: str, turma: str, data_entrada: date, contato: str = "") -> None:
        self.adicionar_alunos([(nome, turma, contato)], data_entrada)

    def adicionar_alunos(self, lista: list[tuple[str, str, str]], data_entrada: date) -> None:
        self.sb.table("alunos").insert(
            [{"nome": n, "turma": t, "contato": c, "data_entrada": data_entrada.isoformat()} for n, t, c in lista]
        ).execute()

    def todas_frequencias(self) -> pd.DataFrame:
        return _df_freq(self._ler_tudo("frequencias"))

    def salvar_frequencias(self, registros: list[dict]) -> None:
        # unique(aluno_id, data) no banco -> regravar o mesmo dia atualiza, não duplica
        self.sb.table("frequencias").upsert(registros, on_conflict="aluno_id,data").execute()


class RepoDemo:
    """Dados em memória (por sessão) para testar sem banco."""

    def __init__(self):
        ss = st.session_state
        if "demo_alunos" not in ss:
            ss.demo_alunos = [
                {"id": i + 1, "nome": n, "turma": t, "data_entrada": INICIO_ANO.isoformat(), "contato": c}
                for i, (n, t, c) in enumerate(_alunos_iniciais())
            ]
            ss.demo_freq = {}  # (aluno_id, data_iso) -> registro

    def listar_alunos(self) -> pd.DataFrame:
        return _df_alunos(st.session_state.demo_alunos)

    def adicionar_aluno(self, nome, turma, data_entrada, contato="") -> None:
        lista = st.session_state.demo_alunos
        lista.append(
            {"id": max([a["id"] for a in lista], default=0) + 1, "nome": nome, "turma": turma,
             "data_entrada": data_entrada.isoformat(), "contato": contato}
        )

    def adicionar_alunos(self, lista, data_entrada) -> None:
        for n, t, c in lista:
            self.adicionar_aluno(n, t, data_entrada, c)

    def todas_frequencias(self) -> pd.DataFrame:
        return _df_freq(list(st.session_state.demo_freq.values()))

    def salvar_frequencias(self, registros) -> None:
        for r in registros:
            st.session_state.demo_freq[(r["aluno_id"], r["data"])] = {"id": len(st.session_state.demo_freq) + 1, **r}

    def gerar_exemplo(self) -> None:
        """Cria 15 dias úteis de chamada fictícia para mostrar o dashboard."""
        random.seed(42)
        dias, d = [], date.today()
        while len(dias) < 15:
            if d.weekday() < 5:
                dias.append(d)
            d -= timedelta(days=1)
        dias.sort()
        freq = {}
        for a in st.session_state.demo_alunos:
            for i, dia in enumerate(dias):
                if a["id"] == 4 and i in (5, 6, 7):          # 3 faltas seguidas
                    s = "falta"
                elif a["id"] == 8:                           # muitas faltas
                    s = random.choices(STATUS_DB, weights=[55, 35, 10])[0]
                else:
                    s = random.choices(STATUS_DB, weights=[86, 6, 8])[0]
                freq[(a["id"], dia.isoformat())] = {
                    "id": len(freq) + 1, "aluno_id": a["id"], "data": dia.isoformat(),
                    "status": s, "observacao": "",
                }
        st.session_state.demo_freq = freq


@st.cache_resource(show_spinner=False)
def _cliente_supabase(url: str, key: str) -> RepoSupabase:
    return RepoSupabase(url, key)


def get_repo():
    try:
        return _cliente_supabase(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"]), "Supabase"
    except Exception:
        return RepoDemo(), "Demonstração"


# ----------------------------------------------------------------------------
# Acesso protegido (opcional): defina [app] senha = "..." nos secrets
# ----------------------------------------------------------------------------
def checar_senha() -> bool:
    try:
        senha = st.secrets["app"]["senha"]
    except Exception:
        return True  # sem senha configurada -> acesso livre
    if st.session_state.get("autenticado"):
        return True
    st.title("📋 Frequência Escolar")
    digitada = st.text_input("Senha de acesso", type="password")
    if digitada:
        if hmac.compare_digest(digitada, senha):
            st.session_state.autenticado = True
            st.rerun()
        st.error("Senha incorreta.")
    return False


if not checar_senha():
    st.stop()

# ----------------------------------------------------------------------------
# Página
# ----------------------------------------------------------------------------
repo, modo = get_repo()
alunos = repo.listar_alunos()
freq_all = repo.todas_frequencias()

st.title("📋 Frequência Escolar")
if not alunos.empty:
    st.caption("Turma: " + ", ".join(sorted(alunos["turma"].unique())))
if modo == "Demonstração":
    st.info("Modo demonstração: a lista de alunos vem da planilha da pasta dados/ e tudo fica só nesta sessão. Configure o Supabase para gravar de verdade.")

if "aviso" in st.session_state:  # mensagem que sobrevive ao st.rerun()
    st.success(st.session_state.pop("aviso"))

tab_chamada, tab_dash, tab_alunos = st.tabs(["📋 Chamada", "📊 Dashboard", "👥 Alunos"])

# ============================ CHAMADA ========================================
with tab_chamada:
    dia = st.date_input("Data da chamada", date.today(), format="DD/MM/YYYY")

    with st.expander("➕ Adicionar aluno (entrou no meio do ano)"):
        with st.form("form_novo_aluno", clear_on_submit=True):
            nome_novo = st.text_input("Nome do aluno")
            turma_nova = st.text_input("Turma", value=alunos["turma"].mode().iat[0] if not alunos.empty else "Turma A")
            contato_novo = st.text_input("Contato (telefone/WhatsApp com DDD)", placeholder="(91) 98888-7777")
            entrada_nova = st.date_input("Data de entrada", date.today(), format="DD/MM/YYYY")
            if st.form_submit_button("Adicionar aluno", width="stretch"):
                nome_limpo = nome_novo.strip()
                if not nome_limpo:
                    st.error("Digite o nome do aluno.")
                elif ((alunos["nome"].str.lower() == nome_limpo.lower()) & (alunos["turma"] == turma_nova.strip())).any():
                    st.warning("Já existe um aluno com esse nome nessa turma.")
                else:
                    repo.adicionar_aluno(nome_limpo, turma_nova.strip() or "Turma A", entrada_nova, so_digitos(contato_novo))
                    st.session_state.aviso = f"Aluno {nome_limpo} adicionado!"
                    st.rerun()

    # só aparecem alunos que já tinham entrado na data da chamada
    alunos_dia = alunos[alunos["data_entrada"] <= dia]
    do_dia = freq_all[freq_all["data"] == dia].set_index("aluno_id")

    dias_lancados = freq_all["data"].nunique()
    st.caption(
        f"{len(alunos_dia)} alunos nesta data · dias já lançados: {dias_lancados}"
        + (" · ✏️ já existe chamada neste dia (salvar atualiza)" if not do_dia.empty else "")
    )
    st.caption("Padrão: Presente. Marque apenas as exceções.")

    if alunos_dia.empty:
        st.warning("Nenhum aluno matriculado nesta data.")
    else:
        with st.form("form_chamada"):
            respostas = []
            for a in alunos_dia.itertuples():
                if a.id in do_dia.index:
                    status_ini = DB_PARA_UI[do_dia.loc[a.id, "status"]]
                    obs_ini = do_dia.loc[a.id, "observacao"]
                else:
                    status_ini, obs_ini = "Presente", ""
                with st.container(border=True):
                    st.markdown(f"**{a.nome}** · {a.turma}  \n{texto_contato(a.contato)}")
                    status = st.radio(
                        "Status", STATUS_UI, index=STATUS_UI.index(status_ini), horizontal=True,
                        key=f"st_{a.id}_{dia.isoformat()}", label_visibility="collapsed",
                    )
                    obs = st.text_input(
                        "Observação", value=obs_ini, placeholder="Observação (opcional)",
                        key=f"ob_{a.id}_{dia.isoformat()}", label_visibility="collapsed",
                    )
                respostas.append((int(a.id), status, obs.strip()))

            if st.form_submit_button("💾 Salvar frequência do dia", type="primary", width="stretch"):
                repo.salvar_frequencias(
                    [
                        {"aluno_id": aid, "data": dia.isoformat(), "status": UI_PARA_DB[s], "observacao": o}
                        for aid, s, o in respostas
                    ]
                )
                st.session_state.aviso = f"Frequência de {dia:%d/%m/%Y} salva ({len(respostas)} alunos)."
                st.rerun()

# ============================ DASHBOARD ======================================
with tab_dash:
    st.subheader("Dashboard de Evasão")

    with st.expander("⚙️ Regras de risco"):
        periodo = st.number_input("Dias do período de análise", 1, 200, 15)
        limite_seq = st.number_input("Faltas seguidas para alerta", 1, 30, 3)
        limite_pct = st.number_input("% de faltas para alerta", 1, 100, 30)
        contar_just = st.checkbox("Contar faltas justificadas no risco", value=False)

    if modo == "Demonstração":
        if st.button("🎲 Gerar 15 dias de exemplo", width="stretch"):
            repo.gerar_exemplo()
            st.rerun()

    if freq_all.empty:
        st.info("Ainda não há chamadas lançadas. Use a aba Chamada.")
    else:
        resumo = resumo_por_aluno(alunos, freq_all, contar_just, float(limite_pct), int(limite_seq))
        dias_lancados = freq_all["data"].nunique()
        em_risco = resumo[resumo["risco"]]

        st.progress(min(dias_lancados / periodo, 1.0), text=f"{dias_lancados} de {periodo} dias lançados")
        if dias_lancados < periodo:
            st.caption("Dashboard parcial: o período ainda não foi concluído.")

        c1, c2 = st.columns(2)
        c1.metric("Alunos", len(alunos))
        c2.metric("🚨 Em risco", len(em_risco))
        c3, c4 = st.columns(2)
        c3.metric("Presença geral", f"{(freq_all['status'] == 'presente').mean() * 100:.1f}%")
        c4.metric("Abaixo de 75% (LDB)", int(resumo["abaixo_ldb"].sum()))

        # --- alerta vermelho
        if em_risco.empty:
            st.success("✅ Nenhum aluno em risco de evasão pelas regras atuais.")
        else:
            linhas = "\n".join(f"- **{r.nome}** — {r.motivo} · {texto_contato(r.contato)}" for r in em_risco.itertuples())
            st.error(f"🚨 **RISCO DE EVASÃO** ({len(em_risco)} aluno(s))\n\n{linhas}")

        # --- gráficos
        g1, g2 = st.columns(2)
        with g1:
            st.markdown("**Top 10 — quem mais faltou**")
            top = resumo.assign(total=resumo["faltas"] + resumo["justificadas"])
            top = top[top["total"] > 0].nlargest(10, "total")
            if top.empty:
                st.caption("Ninguém faltou até agora. 🎉")
            else:
                longo = top.melt(id_vars="nome", value_vars=["faltas", "justificadas"],
                                 var_name="tipo", value_name="qtd")
                longo["tipo"] = longo["tipo"].map({"faltas": "Falta", "justificadas": "Falta Justificada"})
                fig = px.bar(longo, y="nome", x="qtd", color="tipo", orientation="h",
                             color_discrete_map=CORES, category_orders={"nome": top["nome"].tolist()},
                             labels={"nome": "", "qtd": "Faltas", "tipo": ""})
                fig.update_yaxes(autorange="reversed")
                fig.update_layout(height=60 + 38 * len(top), margin=dict(l=0, r=0, t=10, b=0),
                                  legend=dict(orientation="h", y=-0.25))
                st.plotly_chart(fig, width="stretch")
        with g2:
            st.markdown("**Presente × Falta × Justificada**")
            pizza = px.pie(distribuicao_status(freq_all), names="status", values="total",
                           color="status", color_discrete_map=CORES, hole=0.4)
            pizza.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0),
                                legend=dict(orientation="h", y=-0.1))
            st.plotly_chart(pizza, width="stretch")

        # --- tabela detalhada
        st.markdown("**Detalhe por aluno**")
        tabela = resumo.assign(
            situacao=resumo["risco"].map({True: "🚨 Risco", False: "✅ OK"})
        )
        tabela["contato"] = tabela["contato"].map(formatar_contato)
        tabela = tabela[["situacao", "nome", "contato", "turma", "dias", "presencas", "faltas", "justificadas",
                         "seq_max", "pct_faltas", "pct_presenca", "motivo"]]
        tabela.columns = ["Situação", "Aluno", "Contato", "Turma", "Dias", "Presenças", "Faltas", "Justificadas",
                          "Máx. seguidas", "% faltas", "% presença", "Motivo"]
        st.dataframe(tabela, width="stretch", hide_index=True)
        st.download_button("⬇️ Baixar CSV", tabela.to_csv(index=False).encode("utf-8-sig"),
                           "frequencia_resumo.csv", "text/csv", width="stretch")

        st.caption(
            "Referência pública: LDB (Lei 9.394/1996), art. 24, VI — frequência mínima de 75% — e art. 12, VIII "
            "(Lei 13.803/2019) — notificação ao Conselho Tutelar."
        )

# ============================ ALUNOS =========================================
with tab_alunos:
    st.subheader(f"Alunos cadastrados ({len(alunos)})")
    lista = alunos.assign(
        contato_fmt=alunos["contato"].map(formatar_contato),
        conferir=alunos["contato"].map(lambda c: "⚠️ conferir" if c and not contato_valido(c) else ""),
    )[["nome", "turma", "contato_fmt", "conferir", "data_entrada"]]
    lista.columns = ["Aluno", "Turma", "Contato", "", "Entrada"]
    st.dataframe(lista, width="stretch", hide_index=True)
    st.caption("Para incluir um aluno novo, use “Adicionar aluno” na aba Chamada.")

    st.divider()
    st.markdown("**📥 Importar lista da turma (.xlsx ou .csv)**")
    arq = st.file_uploader("Planilha com as colunas “NOME DO ALUNO” e “CONTATO”", type=["xlsx", "csv"])
    if arq is not None:
        try:
            lidos = ler_planilha_alunos(arq)
        except Exception as e:
            st.error(f"Não consegui ler a planilha: {e}")
        else:
            ja = set(zip(alunos["nome"].str.lower(), alunos["turma"]))
            novos = lidos[[(n.lower(), t) not in ja for n, t in zip(lidos["nome"], lidos["turma"])]]
            st.write(f"{len(lidos)} nomes na planilha · {len(novos)} ainda não cadastrados.")
            if not novos.empty:
                conferir = novos[(novos["contato"] != "") & ~novos["contato"].map(contato_valido)]
                if not conferir.empty:
                    st.warning("Conferir o número de contato de: " + ", ".join(conferir["nome"]))
                st.dataframe(novos.assign(contato=novos["contato"].map(formatar_contato)),
                             width="stretch", hide_index=True)
                entrada_imp = st.date_input("Data de entrada deles", INICIO_ANO, format="DD/MM/YYYY", key="entrada_imp")
                if st.button("Importar alunos", type="primary", width="stretch"):
                    repo.adicionar_alunos(list(zip(novos["nome"], novos["turma"], novos["contato"])), entrada_imp)
                    st.session_state.aviso = f"{len(novos)} aluno(s) importado(s)."
                    st.rerun()
