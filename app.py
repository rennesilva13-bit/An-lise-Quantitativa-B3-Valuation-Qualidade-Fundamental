"""
B3 Pro Analyzer - Brapi Edition (Debug & Fix)
=============================================
Correções:
1. Slider de Margem inicia em -100 (para não esconder ações sem dados).
2. Adicionado "Modo Debug" para visualizar o retorno da API.
3. Tratamento para exibir linhas mesmo com fundamentos zerados.

Token: rxNx6YXRYuEkQFDAc66r3C
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import warnings

# Ignorar avisos
warnings.filterwarnings('ignore')

# --- Configuração da Página ---
st.set_page_config(
    page_title="B3 Pro Valuation",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS Customizado ---
st.markdown("""
<style>
    .main-header { font-size: 2rem; font-weight: bold; color: #0066cc; text-align: center; margin-bottom: 1rem; }
    div[data-testid="stMetric"] {
        background-color: #ffffff !important;
        border-radius: 10px; padding: 15px; 
        border: 1px solid #e0e0e0;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    img { border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

class BrapiClient:
    def __init__(self):
        # SEU TOKEN NOVO
        self.token = "rxNx6YXRYuEkQFDAc66r3C"
        self.base_url = "https://brapi.dev/api"
        
        self.tickers_padrao = [
            'BBAS3', 'ITUB4', 'BBDC4', 'SANB11', 'TAEE11', 'TRPL4', 'CPLE6', 'EGIE3',
            'VALE3', 'CSNA3', 'GGBR4', 'WEGE3', 'PSSA3', 'BBSE3', 'CXSE3', 'SAPR11',
            'CMIG4', 'KLBN11', 'SUZB3', 'PRIO3', 'PETR4', 'JBSS3', 'MRFG3', 'GOAU4'
        ]

    def _tratar_lista_tickers(self, tickers_list):
        clean_list = []
        for t in tickers_list:
            t_clean = t.replace("'", "").replace('"', "").replace(",", "").replace(";", "").strip().upper()
            if t_clean:
                t_clean = t_clean.replace(".SA", "")
                clean_list.append(t_clean)
        return clean_list

    def calcular_rsi(self, precos_historicos, window=14):
        try:
            if not precos_historicos or len(precos_historicos) < window: return 50
            series = pd.Series(precos_historicos)
            delta = series.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            res = rsi.iloc[-1]
            return 50 if pd.isna(res) else res
        except:
            return 50

    def buscar_dados_batch(self, tickers):
        tickers_limpos = self._tratar_lista_tickers(tickers)
        if not tickers_limpos: return pd.DataFrame(), None

        tickers_str = ",".join(tickers_limpos)
        
        headers = {'Authorization': f'Bearer {self.token}'}
        params = {
            'fundamental': 'true', 
            'dividends': 'true',
            'range': '1mo',
            'interval': '1d',
        }
        
        try:
            url = f"{self.base_url}/quote/{tickers_str}"
            response = requests.get(url, headers=headers, params=params, timeout=20)
            
            # DEBUG: Retorna o JSON cru também para visualizarmos
            data_json = response.json()
            
            if response.status_code != 200:
                st.error(f"Erro Brapi: {response.status_code} - {response.text}")
                return pd.DataFrame(), data_json

            if 'results' not in data_json:
                return pd.DataFrame(), data_json
            
            resultados = []
            
            for stock in data_json['results']:
                try:
                    ticker = stock.get('symbol', 'N/A')
                    price = stock.get('regularMarketPrice')
                    
                    if price is None or price == 0:
                        continue
                        
                    logo = stock.get('logourl', 'https://brapi.dev/favicon.ico')
                    
                    # Extração de Fundamentos (Tentativa robusta)
                    pl = stock.get('priceToEarnings', 0) or 0
                    lpa = stock.get('earningsPerShare', 0) or 0
                    
                    # Tenta pegar VPA de várias formas
                    vpa = stock.get('bookValuePerShare', 0)
                    if not vpa: vpa = stock.get('bookValue', 0)
                    
                    # Dividendos
                    dy_raw = stock.get('dividendYield', 0) or 0
                    dy_decimal = dy_raw / 100 if dy_raw > 1 else dy_raw
                    
                    roe = stock.get('returnOnEquity', 0) or 0
                    volume = stock.get('regularMarketVolume', 0) or 0
                    
                    # Cálculos
                    valor_graham = 0
                    ms_graham = -100 # Default ruim se falhar conta
                    
                    if lpa > 0 and vpa > 0:
                        valor_graham = np.sqrt(22.5 * lpa * vpa)
                        ms_graham = ((valor_graham - price) / price) * 100
                    
                    dy_reais = price * dy_decimal
                    valor_bazin = dy_reais / 0.06 if dy_reais > 0 else 0
                    
                    rsi = 50
                    hist = stock.get('historicalDataPrice', [])
                    if hist:
                        closes = [d.get('close') for d in hist if d.get('close')]
                        rsi = self.calcular_rsi(closes)
                    
                    # Detecção de Armadilhas
                    motivo_trap = []
                    is_trap = False
                    if roe != 0 and roe < 0.05: motivo_trap.append("ROE Baixo")
                    if volume < 50000: motivo_trap.append("Baixa Liquidez")
                    if motivo_trap: is_trap = True

                    resultados.append({
                        'Logo': logo,
                        'Ticker': ticker,
                        'Preço': price,
                        'V. Graham': valor_graham,
                        'MS Graham (%)': ms_graham,
                        'DY (%)': dy_decimal * 100,
                        'P/L': pl,
                        'VPA': vpa, # Adicionei VPA para debug
                        'LPA': lpa, # Adicionei LPA para debug
                        'ROE (%)': roe * 100,
                        'IFR (14)': rsi,
                        'Armadilha': "⚠️ SIM" if is_trap else "🛡️ NÃO",
                        'Alertas': ", ".join(motivo_trap) if motivo_trap else "OK",
                        'Score Magic': 0
                    })
                    
                except Exception as e:
                    print(f"Erro parse {stock.get('symbol')}: {e}")
                    continue
            
            return pd.DataFrame(resultados), data_json
            
        except Exception as e:
            st.error(f"Erro Conexão: {e}")
            return pd.DataFrame(), None

    def calcular_magic_score(self, df):
        if df.empty: return df
        df = df.copy()
        mask = df['P/L'] > 0
        if not mask.any(): return df

        df.loc[mask, 'Rank_PL'] = df.loc[mask, 'P/L'].rank(ascending=True)
        df.loc[mask, 'Rank_ROE'] = df.loc[mask, 'ROE (%)'].replace(0, -999).rank(ascending=False)
        df['Magic_Points'] = df['Rank_PL'] + df['Rank_ROE']
        min_p, max_p = df['Magic_Points'].min(), df['Magic_Points'].max()
        if max_p != min_p:
            df['Score Magic'] = 100 * (1 - (df['Magic_Points'] - min_p) / (max_p - min_p))
        else:
            df['Score Magic'] = 50
        return df.sort_values('Score Magic', ascending=False).fillna(0)

def main():
    st.markdown('<div class="main-header">💎 B3 Pro: Brapi Edition</div>', unsafe_allow_html=True)
    
    client = BrapiClient()
    
    st.sidebar.header("⚙️ Controle")
    entrada = st.sidebar.radio("Ativos:", ["Carteira Sugerida", "Minha Lista"])
    
    if entrada == "Carteira Sugerida":
        tickers = client.tickers_padrao
    else:
        text = st.sidebar.text_area("Digite os tickers:", "PETR4, VALE3, CMIG4")
        if text:
            tickers = text.split(',')
        else:
            tickers = []

    st.sidebar.divider()
    f_armadilha = st.sidebar.checkbox("Ocultar 'Armadilhas'", False) # Padrão FALSE
    
    # SLIDER AJUSTADO: Começa em -100 para mostrar tudo
    min_ms = st.sidebar.slider("Margem Graham Mínima %", -100, 100, -100)
    
    # DEBUG TOGGLE
    debug_mode = st.sidebar.toggle("🛠️ Modo Debug (Ver JSON)", False)
    
    if st.sidebar.button("🚀 Consultar API"):
        if not tickers:
            st.warning("Defina tickers.")
            return
            
        with st.spinner("Buscando dados..."):
            df, raw_json = client.buscar_dados_batch(tickers)
        
        # MOSTRAR DEBUG SE ATIVADO
        if debug_mode and raw_json:
            st.markdown("### 🛠️ Resposta Bruta da API")
            st.json(raw_json)

        if df.empty:
            st.error("Nenhum dado processável encontrado.")
            if raw_json:
                st.warning("A API respondeu, mas os dados podem estar incompletos (veja Debug).")
            return

        df = client.calcular_magic_score(df)
        
        # Filtros
        view = df.copy()
        if f_armadilha:
            view = view[view['Armadilha'].str.contains("NÃO")]
        
        view = view[view['MS Graham (%)'] >= min_ms]

        st.subheader(f"🎯 Resultados ({len(view)})")
        
        if view.empty:
            st.warning("Nenhuma ação sobrou após os filtros. Tente diminuir o Slider de Margem.")
        else:
            st.dataframe(
                view[['Logo', 'Ticker', 'Preço', 'V. Graham', 'MS Graham (%)', 'P/L', 'LPA', 'VPA', 'Score Magic']],
                column_config={
                    "Logo": st.column_config.ImageColumn("Logo", width="small"),
                    "Preço": st.column_config.NumberColumn(format="R$ %.2f"),
                    "V. Graham": st.column_config.NumberColumn(format="R$ %.2f"),
                    "MS Graham (%)": st.column_config.NumberColumn(format="%.1f%%"),
                    "Score Magic": st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100),
                },
                hide_index=True,
                use_container_width=True
            )
            
            st.info("Nota: Se V. Graham for 0, é porque a API retornou LPA ou VPA zerado/nulo para essa ação.")

if __name__ == "__main__":
    main()
