# dados.py
import os
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

NOME_ARQUIVO_FINAL = "lotofacil.xlsx"


def atualizar_dados():
  """Executa a raspagem via Selenium em modo headless, baixa/atualiza o 'lotofacil.xlsx'

  com as colunas filtradas e retorna o DataFrame.
  """
  pasta_projeto = os.getcwd()
  caminho_arquivo_final = os.path.join(pasta_projeto, NOME_ARQUIVO_FINAL)

  chrome_options = webdriver.ChromeOptions()
  chrome_options.add_argument("--headless=new")
  chrome_options.add_argument("--disable-gpu")
  chrome_options.add_argument("--window-size=1920,1080")
  chrome_options.add_argument(
      "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
  )

  chrome_options.add_experimental_option(
      "prefs",
      {
          "download.default_directory": pasta_projeto,
          "download.prompt_for_download": False,
          "download.directory_upgrade": True,
          "safebrowsing.enabled": True,
      },
  )

  arquivos_antes = set(os.listdir(pasta_projeto))

  driver = webdriver.Chrome(
      service=Service(ChromeDriverManager().install()), options=chrome_options
  )

  arquivo_baixado = None

  try:
    print("🌐 Verificando novos resultados em segundo plano...")
    url = "https://loterias.caixa.gov.br/Paginas/Lotofacil.aspx"
    driver.get(url)

    wait = WebDriverWait(driver, 15)
    botao = wait.until(EC.presence_of_element_located((By.ID, "btnResultados")))

    driver.execute_script(
        "arguments[0].scrollIntoView({block: 'center'});", botao
    )
    time.sleep(1)
    driver.execute_script("arguments[0].click();", botao)

    # Aguarda o download ser concluído na pasta
    for _ in range(15):
      time.sleep(1)
      arquivos_depois = set(os.listdir(pasta_projeto))
      novos_arquivos = arquivos_depois - arquivos_antes

      arquivos_validos = [
          f
          for f in novos_arquivos
          if not f.endswith(".crdownload") and f != NOME_ARQUIVO_FINAL
      ]
      if arquivos_validos:
        arquivo_baixado = os.path.join(pasta_projeto, arquivos_validos[0])
        break

  finally:
    driver.quit()

  if arquivo_baixado and os.path.exists(arquivo_baixado):
    print("🔄 Processando dados e atualizando 'lotofacil.xlsx'...")

    try:
      if arquivo_baixado.endswith(".html") or arquivo_baixado.endswith(".zip"):
        df_lista = pd.read_html(arquivo_baixado)
        df = df_lista[0]
      else:
        try:
          df = pd.read_excel(arquivo_baixado)
        except Exception:
          df_lista = pd.read_html(arquivo_baixado)
          df = df_lista[0]

      colunas_desejadas = [
          "Concurso",
          "Data Sorteio",
          "Bola1",
          "Bola2",
          "Bola3",
          "Bola4",
          "Bola5",
          "Bola6",
          "Bola7",
          "Bola8",
          "Bola9",
          "Bola10",
          "Bola11",
          "Bola12",
          "Bola13",
          "Bola14",
          "Bola15",
      ]

      df.columns = [str(col).strip() for col in df.columns]
      colunas_presentes = [c for c in colunas_desejadas if c in df.columns]
      df_filtrado = df[colunas_presentes]

      # Atualiza o arquivo local
      df_filtrado.to_excel(caminho_arquivo_final, index=False)
      print(f"✅ Arquivo '{NOME_ARQUIVO_FINAL}' atualizado com sucesso!")
      return df_filtrado

    finally:
      if os.path.exists(arquivo_baixado):
        os.remove(arquivo_baixado)
  else:
    # Se falhar o download no momento, lê o arquivo salvo caso ele exista
    if os.path.exists(caminho_arquivo_final):
      return pd.read_excel(caminho_arquivo_final)
    raise Exception("Não foi possível baixar nem ler a base da Lotofácil.")