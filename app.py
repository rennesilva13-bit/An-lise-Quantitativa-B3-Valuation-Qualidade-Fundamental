"""
B3 Pro Analyzer - Brapi Edition (Math Fix)
==========================================
Correção Final:
- Engenharia reversa de dados:
  - Se faltar VPA, calcula via Preço / (P/VP).
  - Se faltar P/L, calcula via Preço / LPA.
- Isso garante que a Fórmula de Graham (Raiz de 22.5 * LPA * VPA) funcione sempre.

Token: rxNx6YXRYuEkQFDAc66r3C
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import warnings
from concurrent.futures import ThreadPoolExecutor

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
        self.token = "rxNx6YXRYuEkQFDAc66r3C"
        self.base_url = "https://brapi.dev/api"
        
        self.tickers_padrao = [
            'BBAS3', 'ITUB4', 'BBDC4', 'SANB11', 'TAEE11', 'TRPL4', 'CPLE6', 'EGIE3',
            'VALE3', 'CSNA3', 'GGBR4', 'WEGE3', 'PSSA3', 'BBSE3', 'CXSE3', 'SAPR11',
            'CMIG4', 'KLBN11', 'SUZB3', 'PRIO3', 'PETR4', 'JBSS3', 'MRFG3', 'GOAU4'
        ]

    def _tratar_ticker(self, ticker):
        return ticker.replace("'", "").replace('"', "").strip().upper().replace(".SA", "")

    def _safe_float(self, value):
        """Converte para float de forma segura, retornando 0 se falhar."""
        try:
            if value is None: return 0.0
            return float(value)
        except:
            return 0.0

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

    def buscar_ativo_individual(self, ticker_raw):
        ticker = self._tratar_ticker(ticker_raw)
        
        headers = {'Authorization': f'Bearer {self.token}'}
        params = {
            'fundamental': 'true', 
            'dividends': 'true',
            'range': '1mo',
            'interval': '1d',
        }
        
        try:
            url = f"{self.base_url}/quote/{ticker}"
            response = requests.get(url, headers=headers, params=params, timeout=10)
            data = response.json()
            
            if 'results' not in data or not data['results']:
                return None
            
            stock = data['results'][0]
            
            # --- Extração de Dados ---
            price = self._safe_float(stock.get('regularMarketPrice'))
            if price == 0: return None
            
            logo = stock.get('logourl', 'https://brapi.dev/favicon.ico')
            
            # 1. Coleta Inicial dos Dados Disponíveis
            pl = self._safe_float(stock.get('priceToEarnings'))
            lpa = self._safe_float(stock.get('earningsPerShare'))
            vpa = self._safe_float(stock.get('bookValuePerShare')) # VPA direto
            if vpa == 0: vpa = self._safe_float(stock.get('bookValue'))
            
            pvp = self._safe_float(stock.get('priceToBook')) # P/VP
            
            # 2. Engenharia Reversa (Math Fix) - O PULO DO GATO 🐱
            
            # Se não tem VPA, mas tem P/VP: VPA = Preço / PVP
            if vpa == 0 and pvp > 0:
                vpa = price / pvp
            
            # Se não tem P/VP, mas tem VPA: PVP = Preço / VPA
            if pvp == 0 and vpa > 0:
                pvp = price / vpa

            # Se não tem LPA, mas tem P/L: LPA = Preço / PL
            if lpa == 0 and pl > 0:
                lpa = price / pl

            # Se não tem P/L, mas tem LPA: PL = Preço / LPA
            if pl == 0 and lpa > 0:
                pl = price / lpa
                
            # 3. Dividendos
            dy_raw = self._safe_float(stock.get('dividendYield'))
            dy_decimal = dy_raw / 100 if dy_raw > 1 else dy_raw
            
            roe = self._safe_float(stock.get('returnOnEquity'))
            volume = self._safe_float(stock.get('regularMarketVolume'))
            
            # --- Cálculos Finais ---
            
            # Graham: Raiz(22.5 * LPA * VPA)
            valor_graham = 0
            ms_graham = -100
            
            if lpa > 0 and vpa > 0:
                valor_graham = np.sqrt(22.5 * lpa * vpa)
                ms_graham = ((valor_graham - price) / price) * 100
            
            # Bazin
            dy_reais = price * dy_decimal
            valor_bazin = dy_reais / 0.06 if dy_reais > 0 else 0
            
            # RSI
            rsi = 50
            hist = stock.get('historicalDataPrice', [])
            if hist:
                closes = [d.get('close') for d in hist if d.get('close')]
                rsi = self.calcular_rsi(closes)
            
            # Armadilhas
            motivo_trap = []
            is_trap = False
            if roe != 0 and roe < 0.05: motivo_trap.append("ROE Baixo")
            if volume < 50000: motivo_trap.append("Baixa Liquidez")
            if motivo_trap: is_trap = True

            return {
                'Logo': logo,
                'Ticker': ticker,
                'Preço': price,
                'V. Graham': valor_graham,
                'MS Graham (%)': ms_graham,
                'DY (%)': dy_decimal * 100,
                'P/L': pl,
                'P/VP': pvp, # Adicionado para visualização
                'VPA': vpa,
                'LPA': lpa,
                'ROE (%)': roe * 100,
                'IFR (14)': rsi,
                'Armadilha': "⚠️ SIM" if is_trap else "🛡️ NÃO",
                'Alertas': ", ".join(motivo_trap) if motivo_trap else "OK",
                'Score Magic': 0
            }

        except Exception as e:
            # print(f"Erro no ativo {ticker}: {e}")
            return None

    def buscar_dados_paralelo(self, tickers_list):
        dados_validos = []
        tickers_clean = [self._tratar_ticker(t) for t in tickers_list if t.strip()]
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(self.buscar_ativo_individual, tickers_clean))
            
        dados_validos = [r for r in results if r is not None]
        return pd.DataFrame(dados_validos)

    def calcular_magic_score(self, df):
        if df.empty: return df
        df = df.copy()
        
        mask = df['P/L'] > 0
        if not mask.any(): 
            df['Score Magic'] = 0
            return df

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
    st.markdown('<div class="main-header">💎 B3 Pro: Brapi Full (Math Fix)</div>', unsafe_allow_html=True)
    
    client = BrapiClient()
    
    st.sidebar.header("⚙️ Controle")
    entrada = st.sidebar.radio("Ativos:", ["Carteira Sugerida", "Minha Lista"])
    
    if entrada == "Carteira Sugerida":
        tickers = client.tickers_padrao
    else:
        text = st.sidebar.text_area("Digite os tickers:", "PETR4, VALE3, CMIG4, BBAS3")
        if text:
            tickers = text.split(',')
        else:
            tickers = []

    st.sidebar.divider()
    f_armadilha = st.sidebar.checkbox("Ocultar 'Armadilhas'", False)
    min_ms = st.sidebar.slider("Margem Graham Mínima %", -100, 100, -100)
    
    if st.sidebar.button("🚀 Consultar API"):
        if not tickers:
            st.warning("Defina tickers.")
            return
            
        with st.spinner(f"Processando {len(tickers)} ativos (Calculando VPA/LPA faltantes)..."):
            df = client.buscar_dados_paralelo(tickers)
        
        if df.empty:
            st.error("Nenhum dado encontrado.")
            return

        df = client.calcular_magic_score(df)
        
        view = df.copy()
        if f_armadilha:
            view = view[view['Armadilha'].str.contains("NÃO")]
        
        view = view[view['MS Graham (%)'] >= min_ms]

        st.subheader(f"🎯 Resultados ({len(view)})")
        
        if view.empty:
            st.warning("Aumente a abrangência dos filtros.")
        else:
            st.dataframe(
                view[['Logo', 'Ticker', 'Preço', 'V. Graham', 'MS Graham (%)', 'P/L', 'P/VP', 'VPA', 'LPA', 'Score Magic']],
                column_config={
                    "Logo": st.column_config.ImageColumn("Logo", width="small"),
                    "Preço": st.column_config.NumberColumn(format="R$ %.2f"),
                    "V. Graham": st.column_config.NumberColumn(format="R$ %.2f"),
                    "MS Graham (%)": st.column_config.NumberColumn(format="%.1f%%"),
                    "Score Magic": st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100),
                    "VPA": st.column_config.NumberColumn(format="%.2f"),
                    "LPA": st.column_config.NumberColumn(format="%.2f"),
                    "P/VP": st.column_config.NumberColumn(format="%.2f"),
                },
                hide_index=True,
                use_container_width=True
            )
            
            st.divider()
            col1, col2 = st.columns([3, 1])
            with col1:
                fig = px.scatter(
                    view, x='MS Graham (%)', y='ROE (%)', 
                    size='Preço', color='Score Magic', 
                    hover_name='Ticker',
                    title="Matriz de Oportunidades",
                    color_continuous_scale='RdYlGn'
                )
                fig.add_vline(x=0, line_dash="dot")
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.success("Nota: Se o VPA não vem da API, ele é calculado agora usando Preço / (P/VP).")

if __name__ == "__main__":
    main()
