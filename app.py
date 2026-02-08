"""
B3 Pro Analyzer - Plutonium Edition (Hybrid Valuation)
======================================================
Novidades:
1. MOTOR HÍBRIDO:
   - Bancos/Seguros -> Avaliados pelo Modelo de Gordon (Dividendos).
   - Empresas Gerais -> Avaliadas por DCF (Fluxo de Caixa).
2. FIX PRIO3/GROWTH: Se FCF < 0, usa Lucro Líquido como proxy para não invalidar o valuation.
3. FORMATÇÃO: Tabelas ajustadas (percentuais e moedas).

Token: rxNx6YXRYuEkQFDAc66r3C
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import plotly.graph_objects as go
import warnings
from concurrent.futures import ThreadPoolExecutor

warnings.filterwarnings('ignore')

# --- Configuração ---
st.set_page_config(
    page_title="B3 Pro Valuation",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS ---
st.markdown("""
<style>
    .main-header { font-size: 2rem; font-weight: bold; color: #0066cc; text-align: center; margin-bottom: 1rem; }
    div[data-testid="stMetric"] {
        background-color: #f8f9fa !important;
        border: 1px solid #dee2e6;
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #0066cc;
    }
    div[data-testid="stMetric"] label { color: #495057 !important; font-size: 14px !important; }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] { color: #212529 !important; font-weight: 700 !important; }
    img { border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

class BrapiClient:
    def __init__(self):
        self.token = "rxNx6YXRYuEkQFDAc66r3C"
        self.base_url = "https://brapi.dev/api"
        
        self.tickers_padrao = [
            'BBAS3', 'ITUB4', 'BBDC4', 'SANB11', 'ABCB4', 'BRSR6', # Financeiro (Gordon)
            'BBSE3', 'CXSE3', 'PSSA3', # Seguros (Gordon)
            'TAEE11', 'TRPL4', 'CPLE6', 'EGIE3', 'ALUP11', 'CMIG4', 
            'VALE3', 'CSNA3', 'GGBR4', 'USIM5', 'GOAU4',
            'WEGE3', 'PRIO3', 'PETR4', 'RECV3',
            'JBSS3', 'MRFG3', 'BEEF3',
            'MGLU3', 'LREN3', 'RDOR3', 'RAIL3', 'TOTS3',
            'SAPR11', 'CSMG3', 'SBSP3'
        ]

    def _tratar_ticker(self, ticker):
        return ticker.replace("'", "").replace('"', "").strip().upper().replace(".SA", "")

    def _safe_float(self, value):
        try:
            if value is None: return 0.0
            val = float(value)
            return val if not np.isnan(val) else 0.0
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
            'modules': 'defaultKeyStatistics,summaryDetail,financialData,summaryProfile,price,incomeStatementHistory', 
            'range': '1y',
            'interval': '1d',
        }
        
        try:
            url = f"{self.base_url}/quote/{ticker}"
            response = requests.get(url, headers=headers, params=params, timeout=15)
            data = response.json()
            
            if 'results' not in data or not data['results']: return None
            stock = data['results'][0]
            
            def buscar_dado(keys_list):
                for k in keys_list:
                    if stock.get(k): return stock.get(k)
                modulos = ['defaultKeyStatistics', 'summaryDetail', 'financialData', 'summaryProfile', 'price', 'incomeStatementHistory']
                for mod in modulos:
                    if mod in stock and isinstance(stock[mod], dict):
                        for k in keys_list:
                            val = stock[mod].get(k)
                            if val is not None: return val
                return 0

            # --- DADOS GERAIS ---
            price = self._safe_float(stock.get('regularMarketPrice'))
            if price == 0: return None
            
            logo = stock.get('logourl', 'https://brapi.dev/favicon.ico')
            setor = stock.get('summaryProfile', {}).get('sector', 'Outros')
            setor_map = {
                'Financial Services': 'Financeiro', 'Utilities': 'Utilidades Púb.',
                'Basic Materials': 'Materiais Básicos', 'Energy': 'Energia',
                'Industrials': 'Industrial', 'Consumer Defensive': 'Consumo N. Cíclico',
                'Consumer Cyclical': 'Consumo Cíclico', 'Technology': 'Tecnologia',
                'Healthcare': 'Saúde', 'Real Estate': 'Imobiliário'
            }
            setor = setor_map.get(setor, setor)

            # --- DADOS PARA VALUATION ---
            shares = self._safe_float(buscar_dado(['sharesOutstanding', 'impliedSharesOutstanding']))
            
            # 1. Fluxo de Caixa (FCF)
            fcf = self._safe_float(buscar_dado(['freeCashflow', 'freeCashFlow']))
            # 2. Lucro Líquido (Net Income) - Fallback para Growth/Bancos
            net_income = self._safe_float(buscar_dado(['netIncome', 'netIncomeToCommon']))
            
            # Se FCF for negativo ou zero, usa Lucro Líquido como Proxy (com desconto de 20% por prudência)
            # Isso salva o valuation da PRIO3 e outras de growth
            fcf_usado = fcf
            metodo_fcf = "FCF Real"
            if fcf <= 0 and net_income > 0:
                fcf_usado = net_income * 0.8 # Proxy Conservadora
                metodo_fcf = "Lucro Líq (Proxy)"
            
            # Dívida
            total_debt = self._safe_float(buscar_dado(['totalDebt']))
            total_cash = self._safe_float(buscar_dado(['totalCash', 'cash']))
            net_debt = total_debt - total_cash

            # --- MÚLTIPLOS ---
            pl = self._safe_float(buscar_dado(['priceToEarnings', 'trailingPE']))
            lpa = self._safe_float(buscar_dado(['earningsPerShare', 'trailingEps']))
            vpa = self._safe_float(buscar_dado(['bookValuePerShare', 'bookValue']))
            pvp = self._safe_float(buscar_dado(['priceToBook', 'priceToBookRatio']))
            divida_ebitda = self._safe_float(buscar_dado(['debtToEbitda']))
            
            # Math Fix
            if vpa == 0 and pvp > 0: vpa = price / pvp
            if lpa == 0 and pl > 0: lpa = price / pl
            
            # Dividendos (Para Modelo de Gordon)
            dy_raw = self._safe_float(buscar_dado(['dividendYield']))
            dy_decimal = dy_raw / 100 if dy_raw > 1 else dy_raw
            div_rate = self._safe_float(buscar_dado(['dividendRate']))
            if div_rate == 0: div_rate = price * dy_decimal # Calcula R$ se faltar

            roe = self._safe_float(buscar_dado(['returnOnEquity']))
            volume = self._safe_float(stock.get('regularMarketVolume'))

            # Graham
            valor_graham = 0
            if lpa > 0 and vpa > 0:
                valor_graham = np.sqrt(22.5 * lpa * vpa)
            
            # Armadilhas
            motivo_trap = []
            if roe != 0 and roe < 0.05: motivo_trap.append("ROE Baixo")
            if divida_ebitda > 5: motivo_trap.append("Dívida Alta")
            if volume < 50000: motivo_trap.append("Iliquidez")

            return {
                'Logo': logo, 'Ticker': ticker, 'Setor': setor, 'Preço': price,
                'V. Graham': valor_graham,
                'DY (%)': dy_decimal * 100, 'P/L': pl, 'ROE (%)': roe * 100,
                'Dívida/EBITDA': divida_ebitda,
                'FCF': fcf_usado, 'Metodo FCF': metodo_fcf, 'Shares': shares, 'Net Debt': net_debt,
                'Net Income': net_income, 'Div Rate (R$)': div_rate,
                'Armadilha': "⚠️ SIM" if motivo_trap else "🛡️ NÃO",
                'Score Magic': 0
            }
        except: return None

    def buscar_dados_paralelo(self, tickers_list):
        tickers_clean = [self._tratar_ticker(t) for t in tickers_list if t.strip()]
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(self.buscar_ativo_individual, tickers_clean))
        return pd.DataFrame([r for r in results if r is not None])

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
        df['Score Magic'] = 100 * (1 - (df['Magic_Points'] - min_p) / (max_p - min_p)) if max_p != min_p else 50
        return df.sort_values('Score Magic', ascending=False).fillna(0)

# --- MOTOR DE VALUATION HÍBRIDO (PLUTONIUM ENGINE) ---
def calcular_valuation_hibrido(row, wacc=0.12, growth=0.06):
    """
    Decide qual modelo usar: Gordon (Bancos) ou DCF (Geral).
    """
    try:
        fair_price = 0
        metodo = "N/A"
        
        # 1. BANCOS E SEGUROS -> MODELO DE GORDON
        if row['Setor'] in ['Financeiro', 'Seguros'] or row['Ticker'] in ['BBAS3', 'ITUB4', 'BBDC4', 'SANB11', 'BBSE3', 'CXSE3', 'PSSA3']:
            metodo = "Gordon (Div)"
            div_rate = row['Div Rate (R$)']
            ke = wacc + 0.02 # Custo de Capital p/ Bancos costuma ser maior ou ajustado
            g = min(growth, 0.04) # Crescimento perpétuo conservador para dividendos
            
            if div_rate > 0 and ke > g:
                fair_price = (div_rate * (1 + g)) / (ke - g)
        
        # 2. GERAL -> DCF (Fluxo de Caixa)
        else:
            metodo = f"DCF ({row.get('Metodo FCF', 'FCF')})"
            fcf = row['FCF']
            shares = row['Shares']
            net_debt = row['Net Debt']
            
            if fcf > 0 and shares > 0:
                # Projeção Simplificada 5 anos
                future_flows = [fcf * ((1 + growth) ** i) for i in range(1, 6)]
                terminal_value = (future_flows[-1] * 1.03) / (wacc - 0.03) # 3% perpétuo fixo
                
                pv_flows = sum([val / ((1 + wacc) ** (i + 1)) for i, val in enumerate(future_flows)])
                pv_terminal = terminal_value / ((1 + wacc) ** 5)
                
                ev = pv_flows + pv_terminal
                equity = ev - net_debt
                fair_price = equity / shares

        # Margem de Segurança
        margin = ((fair_price - row['Preço']) / row['Preço']) * 100 if fair_price > 0 else -100
        return fair_price, margin, metodo

    except:
        return 0, -100, "Erro"

def main():
    st.markdown('<div class="main-header">💎 B3 Pro: Plutonium (Hybrid)</div>', unsafe_allow_html=True)
    
    client = BrapiClient()
    
    if 'dados_b3' not in st.session_state:
        st.session_state['dados_b3'] = pd.DataFrame()

    st.sidebar.header("⚙️ Controle")
    entrada = st.sidebar.radio("Ativos:", ["Carteira Sugerida", "Minha Lista"])
    
    if entrada == "Carteira Sugerida":
        tickers = client.tickers_padrao
    else:
        text = st.sidebar.text_area("Digite os tickers:", "BBAS3, PRIO3, WEGE3")
        if text: tickers = text.split(',')
        else: tickers = []

    st.sidebar.subheader("📊 Premissas Gerais")
    global_wacc = st.sidebar.slider("Taxa de Desconto (WACC/Ke) %", 8.0, 20.0, 13.0, 0.5) / 100
    global_growth = st.sidebar.slider("Crescimento (Growth) %", 0.0, 15.0, 7.0, 0.5) / 100
    
    if st.sidebar.button("🚀 Processar Valuation Inteligente"):
        if not tickers: st.warning("Defina tickers.")
        else:
            with st.spinner("Motor Híbrido: Calculando Gordon (Bancos) e DCF (Geral)..."):
                df_new = client.buscar_dados_paralelo(tickers)
                if not df_new.empty:
                    df_new = client.calcular_magic_score(df_new)
                    
                    # Aplica Valuation Híbrido
                    val_results = df_new.apply(
                        lambda x: calcular_valuation_hibrido(x, wacc=global_wacc, growth=global_growth), 
                        axis=1, result_type='expand'
                    )
                    df_new['Preço Justo (Híbrido)'] = val_results[0]
                    df_new['Margem (%)'] = val_results[1]
                    df_new['Modelo Usado'] = val_results[2]
                    
                    st.session_state['dados_b3'] = df_new
                    st.success("Cálculos Realizados!")
                else: 
                    st.error("Erro na coleta de dados.")

    st.sidebar.divider()
    f_armadilha = st.sidebar.checkbox("Ocultar 'Armadilhas'", False)
    
    if not st.session_state['dados_b3'].empty:
        df = st.session_state['dados_b3']
        view = df.copy()
        if f_armadilha: view = view[view['Armadilha'].str.contains("NÃO")]
        
        tab1, tab2 = st.tabs(["🏆 Ranking Valuation (Híbrido)", "🏢 Comparação Setorial"])
        
        with tab1:
            st.subheader("Oportunidades (Gordon + DCF)")
            st.markdown(
                """
                - 🏦 **Bancos/Seguros:** Avaliados por Dividendos (Gordon).
                - 🏭 **Indústria/Varejo:** Avaliados por Fluxo de Caixa (DCF).
                - 🚀 **Growth (ex: PRIO3):** Ajuste automático para usar Lucro se FCF < 0.
                """
            )
            
            st.dataframe(
                view[['Logo', 'Ticker', 'Setor', 'Preço', 'Preço Justo (Híbrido)', 'Margem (%)', 'Modelo Usado', 'P/L', 'Score Magic']],
                column_config={
                    "Logo": st.column_config.ImageColumn("Logo", width="small"),
                    "Preço": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Preço Justo (Híbrido)": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Margem (%)": st.column_config.NumberColumn(format="%.1f%%"),
                    "Score Magic": st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100),
                },
                hide_index=True, use_container_width=True
            )
        
        with tab2:
            st.subheader("Análise Setorial 🍎")
            setores = sorted(view['Setor'].astype(str).unique())
            setor_sel = st.selectbox("Setor:", setores)
            df_sec = view[view['Setor'] == setor_sel].sort_values('Score Magic', ascending=False)
            
            if not df_sec.empty:
                st.dataframe(
                    df_sec[['Ticker', 'Preço', 'Margem (%)', 'P/L', 'ROE (%)', 'Dívida/EBITDA']],
                    column_config={
                        "Margem (%)": st.column_config.NumberColumn(format="%.1f%%"),
                        "P/L": st.column_config.NumberColumn(format="%.1f"),
                        "ROE (%)": st.column_config.NumberColumn(format="%.1f%%"),
                        "Dívida/EBITDA": st.column_config.NumberColumn(format="%.2f"),
                        "Preço": st.column_config.NumberColumn(format="R$ %.2f"),
                    },
                    hide_index=True, use_container_width=True
                )
    else:
        st.info("👈 Clique em 'Processar Valuation Inteligente'.")

if __name__ == "__main__":
    main()
