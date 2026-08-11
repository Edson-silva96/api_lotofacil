# app.py
import os
from apscheduler.schedulers.background import BackgroundScheduler
from dados import atualizar_dados
from flask import Flask, jsonify, request
import pandas as pd

app = Flask(__name__)

# Configuração do agendador em segundo plano para produção
# Atualiza a base via Selenium automaticamente a cada 6 horas
scheduler = BackgroundScheduler()
scheduler.add_job(func=atualizar_dados, trigger="interval", hours=6)
scheduler.start()

ARQUIVO_LOCAL = "lotofacil.xlsx"


def carregar_dados_locais():
  """Carrega a planilha local em memória.

  Se o arquivo ainda não existir no servidor, força a execução da raspagem.
  """
  if os.path.exists(ARQUIVO_LOCAL):
    try:
      return pd.read_excel(ARQUIVO_LOCAL)
    except Exception:
      return atualizar_dados()
  else:
    return atualizar_dados()


def sanitizar_dataframe(df):
  """Remove linhas de rodapé/sujeiras e garante conversão das dezenas para inteiros."""
  df = df.copy()
  df["Concurso"] = pd.to_numeric(df["Concurso"], errors="coerce")
  df = df.dropna(subset=["Concurso"])

  colunas_bolas = [col for col in df.columns if str(col).startswith("Bola")]
  for col in colunas_bolas:
    df[col] = pd.to_numeric(df[col], errors="coerce")

  return df, colunas_bolas


# ROTA 1: Ranking dos números mais sorteados
@app.route("/api/numeros-frequentes", methods=["GET"])
def numeros_mais_saem():
  try:
    df = carregar_dados_locais()
    df, colunas_bolas = sanitizar_dataframe(df)

    todas_as_bolas = df[colunas_bolas].values.flatten()
    serie_bolas = pd.Series(todas_as_bolas).dropna()
    frequencia = serie_bolas.value_counts()

    resultado = [
        {"numero": int(num), "frequencia": int(qtd)}
        for num, qtd in frequencia.items()
    ]

    return (
        jsonify({
            "status": "sucesso",
            "total_concursos": int(len(df)),
            "ranking_numeros": resultado,
        }),
        200,
    )
  except Exception as e:
    return jsonify({"status": "erro", "mensagem": str(e)}), 500


# ROTA 2: 5 últimos sorteios
@app.route("/api/ultimos-sorteios", methods=["GET"])
def ultimos_sorteios():
  try:
    df = carregar_dados_locais()
    df, _ = sanitizar_dataframe(df)

    df_ultimos = df.tail(5).iloc[::-1]

    resultado = []
    for _, row in df_ultimos.iterrows():
      item = {}
      for col in df.columns:
        val = row[col]
        if pd.isna(val):
          item[col] = None
        elif isinstance(val, (float, int)):
          item[col] = int(val)
        else:
          item[col] = str(val)
      resultado.append(item)

    return (
        jsonify({
            "status": "sucesso",
            "quantidade": len(resultado),
            "ultimos_sorteios": resultado,
        }),
        200,
    )
  except Exception as e:
    return jsonify({"status": "erro", "mensagem": str(e)}), 500


# ROTA 3: Agrupamento sequencial (Bola1 a Bola15) com porcentagens
@app.route("/api/agrupar", methods=["GET", "POST"])
def agrupar_colunas():
  try:
    df = carregar_dados_locais()
    df, colunas_bolas = sanitizar_dataframe(df)

    total_concursos = int(len(df))
    if total_concursos == 0:
      return (
          jsonify(
              {"status": "erro", "mensagem": "Base de dados está vazia."}
          ),
          400,
      )

    colunas_ordenadas = sorted(
        colunas_bolas,
        key=lambda x: (
            int(x.replace("Bola", ""))
            if x.replace("Bola", "").isdigit()
            else 99
        ),
    )

    resultado = {}
    for col in colunas_ordenadas:
      frequencia = df[col].value_counts().reset_index()
      frequencia.columns = ["valor", "total"]
      frequencia = frequencia.sort_values(by="valor")

      lista_detalhes = []
      for _, row in frequencia.iterrows():
        val = row["valor"]
        qtd = int(row["total"])
        if pd.isna(val):
          continue

        val_limpo = int(val) if isinstance(val, (int, float)) else str(val)
        porcentagem = round((qtd / total_concursos) * 100, 2)

        lista_detalhes.append({
            "numero": val_limpo,
            "total_saidas": qtd,
            "porcentagem": f"{porcentagem}%",
            "porcentagem_num": porcentagem,
        })
      resultado[col] = lista_detalhes

    return (
        jsonify({
            "status": "sucesso",
            "total_concursos": total_concursos,
            "dados": resultado,
        }),
        200,
    )
  except Exception as e:
    return jsonify({"status": "erro", "mensagem": str(e)}), 500


# ROTA 4: Atraso atual das dezenas (1 a 25)
@app.route("/api/atrasos", methods=["GET"])
def atraso_dezenas():
  try:
    df = carregar_dados_locais()
    df, colunas_bolas = sanitizar_dataframe(df)

    ultimo_concurso = int(df["Concurso"].max())
    atrasos = []

    for num in range(1, 26):
      mascara = (df[colunas_bolas] == num).any(axis=1)
      df_num = df[mascara]

      if not df_num.empty:
        ultimo_concurso_num = int(df_num["Concurso"].max())
        atraso = ultimo_concurso - ultimo_concurso_num
      else:
        atraso = ultimo_concurso

      atrasos.append({"numero": num, "atraso_concursos": atraso})

    atrasos_ordenados = sorted(
        atrasos, key=lambda x: x["atraso_concursos"], reverse=True
    )

    return (
        jsonify({
            "status": "sucesso",
            "ultimo_concurso_base": ultimo_concurso,
            "atrasos": atrasos_ordenados,
        }),
        200,
    )
  except Exception as e:
    return jsonify({"status": "erro", "mensagem": str(e)}), 500


# ROTA 5: Proporção histórica de Pares / Ímpares
@app.route("/api/pares-impares", methods=["GET"])
def pares_impares():
  try:
    df = carregar_dados_locais()
    df, colunas_bolas = sanitizar_dataframe(df)

    distribuicao = {}
    for _, row in df[colunas_bolas].iterrows():
      dezenas = [int(v) for v in row.dropna() if isinstance(v, (int, float))]
      qtd_pares = sum(1 for d in dezenas if d % 2 == 0)
      qtd_impares = len(dezenas) - qtd_pares

      chave = f"{qtd_impares} ímpares / {qtd_pares} pares"
      distribuicao[chave] = distribuicao.get(chave, 0) + 1

    total_concursos = len(df)
    resultado = [
        {
            "padrao": k,
            "frequencia": v,
            "porcentagem": f"{round((v / total_concursos) * 100, 2)}%",
        }
        for k, v in sorted(
            distribuicao.items(), key=lambda x: x[1], reverse=True
        )
    ]

    return (
        jsonify({
            "status": "sucesso",
            "total_concursos": total_concursos,
            "padroes": resultado,
        }),
        200,
    )
  except Exception as e:
    return jsonify({"status": "erro", "mensagem": str(e)}), 500


# ROTA 6: Conferidor de Apostas (POST)
@app.route("/api/conferir", methods=["POST"])
def conferir_jogo():
  try:
    dados_json = request.get_json(silent=True) or {}
    dezenas_usuario = dados_json.get("dezenas")

    if (
        not dezenas_usuario
        or not isinstance(dezenas_usuario, list)
        or len(dezenas_usuario) != 15
    ):
      return (
          jsonify({
              "status": "erro",
              "mensagem": (
                  "Envie uma lista com 15 dezenas em JSON: {"
                  '"dezenas": [1, 2, ...]}'
              ),
          }),
          400,
      )

    set_usuario = set(map(int, dezenas_usuario))

    df = carregar_dados_locais()
    df, colunas_bolas = sanitizar_dataframe(df)

    resumo_acertos = {11: 0, 12: 0, 13: 0, 14: 0, 15: 0}
    concursos_premiados = []

    for _, row in df.iterrows():
      dezenas_sorteio = set(row[colunas_bolas].dropna().astype(int))
      acertos = len(set_usuario.intersection(dezenas_sorteio))

      if acertos >= 11:
        resumo_acertos[acertos] += 1
        if acertos >= 14:
          concursos_premiados.append({
              "concurso": int(row["Concurso"]),
              "data": str(row.get("Data Sorteio", "")),
              "acertos": acertos,
          })

    return (
        jsonify({
            "status": "sucesso",
            "jogo_conferido": sorted(list(set_usuario)),
            "resumo_premiacoes": resumo_acertos,
            "destaques_14_15_pontos": concursos_premiados,
        }),
        200,
    )
  except Exception as e:
    return jsonify({"status": "erro", "mensagem": str(e)}), 500


# ROTA 7: Estatística de repetição do concurso anterior
@app.route("/api/repetidos", methods=["GET"])
def repetidos_concurso_anterior():
  try:
    df = carregar_dados_locais()
    df, colunas_bolas = sanitizar_dataframe(df)

    df = df.sort_values(by="Concurso").reset_index(drop=True)

    if len(df) < 2:
      return (
          jsonify(
              {"status": "erro", "mensagem": "Dados suficientes ausentes."}
          ),
          400,
      )

    distribuicao_repeticoes = {}
    total_comparacoes = 0
    soma_repeticoes = 0

    for i in range(1, len(df)):
      sorteio_anterior = set(df.loc[i - 1, colunas_bolas].dropna().astype(int))
      sorteio_atual = set(df.loc[i, colunas_bolas].dropna().astype(int))

      qtd_repetidas = len(sorteio_atual.intersection(sorteio_anterior))
      distribuicao_repeticoes[qtd_repetidas] = (
          distribuicao_repeticoes.get(qtd_repetidas, 0) + 1
      )
      soma_repeticoes += qtd_repetidas
      total_comparacoes += 1

    media_historica = (
        round(soma_repeticoes / total_comparacoes, 2)
        if total_comparacoes > 0
        else 0
    )

    estatisticas = []
    for qtd in sorted(distribuicao_repeticoes.keys()):
      total_ocorrencias = distribuicao_repeticoes[qtd]
      porcentagem = round((total_ocorrencias / total_comparacoes) * 100, 2)
      estatisticas.append({
          "dezenas_repetidas": int(qtd),
          "frequencia": int(total_ocorrencias),
          "porcentagem": f"{porcentagem}%",
          "porcentagem_num": porcentagem,
      })

    return (
        jsonify({
            "status": "sucesso",
            "total_comparacoes": total_comparacoes,
            "media_historica_repeticao": media_historica,
            "distribuicao": estatisticas,
        }),
        200,
    )
  except Exception as e:
    return jsonify({"status": "erro", "mensagem": str(e)}), 500


# ROTA 8: Consulta individual por concurso
@app.route("/api/concurso/<int:numero>", methods=["GET"])
def buscar_concurso(numero):
  try:
    df = carregar_dados_locais()
    df, colunas_bolas = sanitizar_dataframe(df)

    df_concurso = df[df["Concurso"] == numero]

    if df_concurso.empty:
      return (
          jsonify({
              "status": "erro",
              "mensagem": f"Concurso {numero} não encontrado.",
          }),
          404,
      )

    linha = df_concurso.iloc[0]

    dados_concurso = {}
    for col in df.columns:
      val = linha[col]
      if pd.isna(val):
        dados_concurso[col] = None
      elif isinstance(val, (float, int)):
        dados_concurso[col] = int(val)
      else:
        dados_concurso[col] = str(val)

    dezenas = [
        dados_concurso[col]
        for col in colunas_bolas
        if dados_concurso.get(col) is not None
    ]

    return (
        jsonify({
            "status": "sucesso",
            "concurso": int(linha["Concurso"]),
            "data_sorteio": dados_concurso.get("Data Sorteio"),
            "dezenas": dezenas,
            "detalhes_completos": dados_concurso,
        }),
        200,
    )
  except Exception as e:
    return jsonify({"status": "erro", "mensagem": str(e)}), 500


# ROTA BÔNUS: Atualização manual sob demanda
@app.route("/api/atualizar-manual", methods=["POST", "GET"])
def atualizar_manual():
  try:
    atualizar_dados()
    return jsonify({"status": "sucesso", "mensagem": "Base atualizada!"}), 200
  except Exception as e:
    return jsonify({"status": "erro", "mensagem": str(e)}), 500


if __name__ == "__main__":
  print("🚀 API Flask da Lotofácil iniciada!")
  app.run(host="0.0.0.0", port=5000, debug=True)