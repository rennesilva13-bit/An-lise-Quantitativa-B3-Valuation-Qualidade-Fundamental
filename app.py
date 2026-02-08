"""
B3 Pro Analyzer - Brapi Edition (Full Data)
===========================================
Correção Crítica:
- Mudança de 'Batch Request' para 'Parallel Individual Request'.
- Isso garante que a API entregue os fundamentos (LPA, VPA, P/L) completos.
- Multithreading para manter a velocidade alta.

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
        """Limpa o ticker para o formato correto."""
        return ticker.replace("'", "").replace('"', "").strip().upper().replace(".SA", "")

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
        """Busca dados completos de UM ativo (para garantir fundamentos)."""
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
            price = stock.get('regularMarketPrice')
            if price is None or price == 0: return None
            
            logo = stock.get('logourl', 'https://brapi.dev/favicon.ico')
            
            # Fundamentos - Tenta extrair da raiz
            pl = stock.get('priceToEarnings', 0)
            lpa = stock.get('earningsPerShare', 0)
            vpa = stock.get('bookValuePerShare', 0)
            
            # Fallbacks: As vezes a Brapi retorna nulo, tentamos calcular
            if pl is None: pl = 0
            if lpa is None: lpa = 0
            if vpa is None or vpa == 0: vpa = stock.get('bookValue', 0) # Tenta outro campo
            
            # Dividendos
            dy_raw = stock.get('dividendYield', 0)
            if dy_raw is None: dy_raw = 0
            dy_decimal = dy_raw / 100 if dy_raw > 1 else dy_raw
            
            roe = stock.get('returnOnEquity', 0)
            if roe is None: roe = 0
            
            volume = stock.get('regularMarketVolume', 0)
            
            # --- Cálculos ---
            # Graham
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
                'VPA': vpa,
                'LPA': lpa,
                'ROE (%)': roe * 100,
                'IFR (14)': rsi,
                'Armadilha': "⚠️ SIM" if is_trap else "🛡️ NÃO",
                'Alertas': ", ".join(motivo_trap) if motivo_trap else "OK",
                'Score Magic': 0
            }

        except Exception as e:
            print(f"Erro no ativo {ticker}: {e}")
            return None

    def buscar_dados_paralelo(self, tickers_list):
        """Usa Multithreading para buscar ativos individualmente (Rápido + Dados Completos)"""
        dados_validos = []
        
        # Limpa lista
        tickers_clean = [self._tratar_ticker(t) for t in tickers_list if t.strip()]
        
        # Executa em paralelo (10 workers)
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(self.buscar_ativo_individual, tickers_clean))
            
        # Filtra Nones
        dados_validos = [r for r in results if r is not None]
        
        return pd.DataFrame(dados_validos)

    def calcular_magic_score(self, df):
        if df.empty: return df
        df = df.copy()
        
        # Só ranqueia quem tem lucro
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
    st.markdown('<div class="main-header">💎 B3 Pro: Brapi Full Data</div>', unsafe_allow_html=True)
    
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
    f_armadilha = st.sidebar.checkbox("Ocultar 'Armadilhas'", False)
    min_ms = st.sidebar.slider("Margem Graham Mínima %", -100, 100, -100)
    
    if st.sidebar.button("🚀 Consultar API (Modo Completo)"):
        if not tickers:
            st.warning("Defina tickers.")
            return
            
        with st.spinner(f"Baixando dados completos de {len(tickers)} ativos..."):
            df = client.buscar_dados_paralelo(tickers)
        
        if df.empty:
            st.error("Nenhum dado encontrado. Verifique conexão ou tickers.")
            return

        df = client.calcular_magic_score(df)
        
        # Filtros
        view = df.copy()
        if f_armadilha:
            view = view[view['Armadilha'].str.contains("NÃO")]
        
        view = view[view['MS Graham (%)'] >= min_ms]

        st.subheader(f"🎯 Resultados ({len(view)})")
        
        if view.empty:
            st.warning("Filtros muito rigorosos. Tente diminuir a margem.")
        else:
            # Tabela Completa
            st.dataframe(
                view[['Logo', 'Ticker', 'Preço', 'V. Graham', 'MS Graham (%)', 'LPA', 'VPA', 'P/L', 'ROE (%)', 'Score Magic']],
                column_config={
                    "Logo": st.column_config.ImageColumn("Logo", width="small"),
                    "Preço": st.column_config.NumberColumn(format="R$ %.2f"),
                    "V. Graham": st.column_config.NumberColumn(format="R$ %.2f"),
                    "MS Graham (%)": st.column_config.NumberColumn(format="%.1f%%"),
                    "Score Magic": st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100),
                    "LPA": st.column_config.NumberColumn(format="%.2f"),
                    "VPA": st.column_config.NumberColumn(format="%.2f"),
                },
                hide_index=True,
                use_container_width=True
            )
            
            # Gráfico Visual
            st.divider()
            col1, col2 = st.columns([3, 1])
            with col1:
                fig = px.scatter(
                    view, x='MS Graham (%)', y='ROE (%)', 
                    size='Preço', color='Score Magic', 
                    hover_name='Ticker',
                    title="Matriz de Oportunidades (Qualidade vs Desconto)",
                    color_continuous_scale='RdYlGn'
                )
                fig.add_vline(x=0, line_dash="dot", annotation_text="Preço Justo")
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.info("Agora os dados de LPA e VPA devem aparecer corretamente, pois estamos consultando ativo por ativo.")

if __name__ == "__main__":
    main()
