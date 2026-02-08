"""
B3 Dividend Pro - Anti-Trap (Math Fix Edition)
==============================================
Correção:
- Cálculo manual de 'Div. 12m (R$)' usando (Preço * Yield) se a API retornar zero.
- Cálculo manual de 'Payout' usando (Div. 12m / LPA) se a API retornar zero.
- Garante que a tabela de Renda Passiva nunca fique vazia.

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

# Ignorar avisos
warnings.filterwarnings('ignore')

# --- Configuração da Página ---
st.set_page_config(
    page_title="B3 Dividend Pro",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS Customizado (Estilo Renda) ---
st.markdown("""
<style>
    .main-header { font-size: 2rem; font-weight: bold; color: #2E8B57; text-align: center; margin-bottom: 1rem; }
    
    div[data-testid="stMetric"] {
        background-color: #f0fff4 !important;
        border: 1px solid #c3e6cb;
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #2E8B57;
    }
    
    div[data-testid="stMetric"] label {
        color: #155724 !important;
        font-size: 14px !important;
    }
    
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #155724 !important;
        font-weight: 700 !important;
    }
    
    img { border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

class BrapiClient:
    def __init__(self):
        self.token = "rxNx6YXRYuEkQFDAc66r3C"
        self.base_url = "https://brapi.dev/api"
        
        # Lista de Dividendos
        self.tickers_padrao = [
            'BBAS3', 'ITUB4', 'BBDC4', 'SANB11', 'ABCB4', 'BRSR6', # Bancos
            'TAEE11', 'TRPL4', 'CPLE6', 'EGIE3', 'ALUP11', 'CMIG4', 'AURE3', # Elétricas
            'BBSE3', 'CXSE3', 'PSSA3', # Seguros
            'SAPR11', 'CSMG3', 'SBSP3', # Saneamento
            'VALE3', 'CSNA3', 'GGBR4', # Commodities
            'PETR4', 'PRIO3', # Petróleo
            'LEVE3', 'TUPY3', 'UNIP6' # Industriais
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

    def buscar_ativo_individual(self, ticker_raw):
        ticker = self._tratar_ticker(ticker_raw)
        headers = {'Authorization': f'Bearer {self.token}'}
        
        params = {
            'fundamental': 'true', 
            'dividends': 'true',
            'modules': 'summaryDetail,defaultKeyStatistics,financialData,summaryProfile,price',
            'range': '1y',
            'interval': '1d',
        }
        
        try:
            url = f"{self.base_url}/quote/{ticker}"
            response = requests.get(url, headers=headers, params=params, timeout=12)
            data = response.json()
            
            if 'results' not in data or not data['results']: return None
            stock = data['results'][0]
            
            def buscar_dado(keys_list):
                for k in keys_list:
                    if stock.get(k): return stock.get(k)
                modulos = ['summaryDetail', 'defaultKeyStatistics', 'financialData', 'price']
                for mod in modulos:
                    if mod in stock and isinstance(stock[mod], dict):
                        for k in keys_list:
                            val = stock[mod].get(k)
                            if val: return val
                return 0

            # 1. Preço
            price = self._safe_float(stock.get('regularMarketPrice'))
            if price == 0: return None
            
            logo = stock.get('logourl', 'https://brapi.dev/favicon.ico')
            setor = stock.get('summaryProfile', {}).get('sector', 'Outros')
            
            # 2. Yield (DY)
            dy_raw = self._safe_float(buscar_dado(['dividendYield', 'trailingAnnualDividendYield']))
            dy_decimal = dy_raw / 100 if dy_raw > 1 else dy_raw
            dy_percent = dy_decimal * 100
            
            # 3. Dividendos em Reais (12m) - Math Fix
            dividend_rate = self._safe_float(buscar_dado(['dividendRate', 'trailingAnnualDividendRate']))
            
            # Se a API não deu o valor em R$, calculamos: Preço * Yield Decimal
            if dividend_rate == 0 and dy_decimal > 0:
                dividend_rate = price * dy_decimal
            
            # 4. Lucro por Ação (LPA)
            lpa = self._safe_float(buscar_dado(['earningsPerShare', 'trailingEps']))
            pl = self._safe_float(buscar_dado(['priceToEarnings', 'trailingPE']))
            
            # 5. Payout Ratio - Math Fix
            payout = self._safe_float(buscar_dado(['payoutRatio']))
            
            # Se a API mandou zero, mas temos Dividendos e Lucro: Payout = Div / LPA
            if payout == 0 and lpa > 0 and dividend_rate > 0:
                payout = dividend_rate / lpa
            
            # Ajuste de escala (se vier 0.5 é 50%, se vier 50 é 50%)
            payout_percent = payout * 100 if payout < 2.5 else payout
            
            # 6. Solvência
            divida_ebitda = self._safe_float(buscar_dado(['debtToEbitda']))
            
            # --- DETECTOR DE ARMADILHA ---
            is_trap = False
            warnings_list = []
            
            # Filtros
            if payout_percent > 110: 
                is_trap = True
                warnings_list.append(f"Payout Explosivo ({payout_percent:.0f}%)")
            
            if lpa < 0:
                is_trap = True
                warnings_list.append("Prejuízo")
                
            if dy_percent > 25:
                warnings_list.append("Yield Anormal (>25%)")
            
            if dy_percent < 0.1:
                warnings_list.append("Não paga")
                
            if divida_ebitda > 5.0:
                warnings_list.append("Dívida Alta")

            return {
                'Logo': logo, 'Ticker': ticker, 'Setor': setor, 'Preço': price,
                'DY (%)': dy_percent,
                'Payout (%)': payout_percent,
                'Div. 12m (R$)': dividend_rate,
                'P/L': pl, 'LPA': lpa, 'Dívida/EBITDA': divida_ebitda,
                'Is Trap': is_trap,
                'Status': "⚠️ CUIDADO" if is_trap else ("🚨 ALERTA" if warnings_list else "✅ SEGURO"),
                'Motivo': ", ".join(warnings_list) if warnings_list else "Sustentável",
                'Score Div': 0
            }
        except: return None

    def buscar_dados_paralelo(self, tickers_list):
        tickers_clean = [self._tratar_ticker(t) for t in tickers_list if t.strip()]
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(self.buscar_ativo_individual, tickers_clean))
        return pd.DataFrame([r for r in results if r is not None])

    def calcular_dividend_score(self, df):
        if df.empty: return df
        df = df.copy()
        
        mask = (df['DY (%)'] > 0)
        if not mask.any(): 
            df['Score Div'] = 0
            return df
            
        # Score Yield (teto 18%)
        df['Yield_Capped'] = df['DY (%)'].clip(upper=18)
        df.loc[mask, 'Rank_Yield'] = df.loc[mask, 'Yield_Capped'].rank(ascending=True)
        
        # Score Payout (Ideal ~60%)
        # Se Payout for 0 (erro de dado), penaliza
        df['Dist_Payout'] = abs(df['Payout (%)'] - 60)
        df.loc[mask, 'Rank_Payout'] = df['Dist_Payout'].rank(ascending=False)
        
        # Score Dívida
        df.loc[mask, 'Rank_Divida'] = df.loc[mask, 'Dívida/EBITDA'].rank(ascending=False)
        
        df['Raw_Score'] = (df['Rank_Yield']*2) + (df['Rank_Payout']*1.5) + (df['Rank_Divida']*1)
        
        min_p, max_p = df['Raw_Score'].min(), df['Raw_Score'].max()
        if max_p != min_p:
            df['Score Div'] = 100 * (df['Raw_Score'] - min_p) / (max_p - min_p)
        else: df['Score Div'] = 50
        
        return df.sort_values('Score Div', ascending=False).fillna(0)

def main():
    st.markdown('<div class="main-header">💰 B3 Dividend Pro: Math Fix</div>', unsafe_allow_html=True)
    
    client = BrapiClient()
    
    if 'dados_div' not in st.session_state:
        st.session_state['dados_div'] = pd.DataFrame()

    st.sidebar.header("⚙️ Carteira")
    entrada = st.sidebar.radio("Ativos:", ["Carteira 'Vacas Leiteiras'", "Minha Carteira"])
    
    if entrada == "Carteira 'Vacas Leiteiras'":
        tickers = client.tickers_padrao
        st.sidebar.info(f"Analisando {len(tickers)} pagadoras.")
    else:
        text = st.sidebar.text_area("Digite os tickers:", "TAEE11, BBSE3, ITSA4")
        if text: tickers = text.split(',')
        else: tickers = []

    if st.sidebar.button("🔄 Atualizar Dados"):
        if not tickers: st.warning("Defina tickers.")
        else:
            with st.spinner("Calculando Payout e Dividendos..."):
                df_new = client.buscar_dados_paralelo(tickers)
                if not df_new.empty:
                    df_new = client.calcular_dividend_score(df_new)
                    st.session_state['dados_div'] = df_new
                    st.success("Dados Calculados com Sucesso!")
                else: st.error("Erro na busca.")

    st.sidebar.divider()
    
    # Filtros
    st.sidebar.subheader("🛡️ Filtros")
    f_trap = st.sidebar.checkbox("Ocultar 'Traps'", value=True)
    min_dy = st.sidebar.slider("DY Mínimo (%)", 0.0, 15.0, 6.0)
    max_payout = st.sidebar.slider("Payout Máximo (%)", 50, 200, 110)
    
    if not st.session_state['dados_div'].empty:
        df = st.session_state['dados_div']
        view = df.copy()
        
        if f_trap: view = view[view['Is Trap'] == False]
        view = view[(view['DY (%)'] >= min_dy) & (view['Payout (%)'] <= max_payout)]
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Média Yield", f"{view['DY (%)'].mean():.1f}%")
        c2.metric("Payout Médio", f"{view['Payout (%)'].mean():.1f}%")
        c3.metric("Ativos Seguros", f"{len(view)}")
        c4.metric("Traps", f"{len(df) - len(view)}", delta_color="inverse")
        
        st.divider()

        tab1, tab2 = st.tabs(["🏆 Ranking", "🔎 Gráficos"])
        
        with tab1:
            st.dataframe(
                view[['Logo', 'Ticker', 'Preço', 'DY (%)', 'Payout (%)', 'Div. 12m (R$)', 'Status', 'Motivo', 'Score Div']],
                column_config={
                    "Logo": st.column_config.ImageColumn("Logo", width="small"),
                    "Preço": st.column_config.NumberColumn(format="R$ %.2f"),
                    "DY (%)": st.column_config.NumberColumn(format="%.1f%%"),
                    "Payout (%)": st.column_config.NumberColumn(format="%.0f%%"), # Agora vai aparecer!
                    "Div. 12m (R$)": st.column_config.NumberColumn(format="R$ %.2f"), # Agora vai aparecer!
                    "Score Div": st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100),
                },
                hide_index=True, use_container_width=True
            )
            
            st.info("Nota: Se a API não informa os dividendos em R$, o sistema agora calcula automaticamente: Preço x Yield.")

        with tab2:
            col_chart, col_legenda = st.columns([3, 1])
            with col_chart:
                fig = px.scatter(
                    view, x='Payout (%)', y='DY (%)',
                    size='Score Div', color='Status',
                    hover_name='Ticker', text='Ticker',
                    title="Matriz de Dividendos (Yield vs Payout)",
                    color_discrete_map={"✅ SEGURO": "green", "⚠️ CUIDADO": "red", "🚨 ALERTA": "orange"},
                    height=500
                )
                fig.add_vrect(x0=100, x1=200, fillcolor="red", opacity=0.1)
                fig.update_traces(textposition='top center')
                st.plotly_chart(fig, use_container_width=True)
            
            with col_legenda:
                st.markdown("**Legenda:**\n\n🟢 Seguro\n🔴 Trap\n🟠 Alerta")

    else:
        st.info("👈 Clique em 'Atualizar Dados'.")

if __name__ == "__main__":
    main()
