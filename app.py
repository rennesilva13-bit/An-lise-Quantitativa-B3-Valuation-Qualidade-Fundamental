"""
B3 Pro Analyzer - Titanium Edition (DCF Master)
===============================================
Novidade Principal: Valuation por Fluxo de Caixa Descontado (DCF).
- Projeção de 2 Estágios (Crescimento + Perpetuidade).
- Matriz de Sensibilidade (WACC vs Growth).
- Cálculo automático do Valor Intrínseco para todas as ações.
- Mantém filtros Anti-Trap e Comparação Setorial.

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
        background-color: #f8f9fa !important;
        border: 1px solid #dee2e6;
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #0066cc;
    }
    
    div[data-testid="stMetric"] label {
        color: #495057 !important;
        font-size: 14px !important;
    }
    
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #212529 !important;
        font-weight: 700 !important;
    }
    
    img { border-radius: 5px; }
    
    /* Tabela de Sensibilidade */
    .dataframe { font-size: 12px !important; }
</style>
""", unsafe_allow_html=True)

class BrapiClient:
    def __init__(self):
        self.token = "rxNx6YXRYuEkQFDAc66r3C"
        self.base_url = "https://brapi.dev/api"
        
        self.tickers_padrao = [
            'BBAS3', 'ITUB4', 'BBDC4', 'SANB11', 'ABCB4', 'BRSR6', 
            'TAEE11', 'TRPL4', 'CPLE6', 'EGIE3', 'ALUP11', 'CMIG4', 
            'VALE3', 'CSNA3', 'GGBR4', 'USIM5', 'GOAU4',
            'WEGE3', 'PSSA3', 'BBSE3', 'CXSE3',
            'SAPR11', 'CSMG3', 'SBSP3',
            'PRIO3', 'PETR4', 'RECV3',
            'JBSS3', 'MRFG3', 'BEEF3',
            'MGLU3', 'LREN3', 'RDOR3', 'RAIL3', 'TOTS3'
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
            'modules': 'defaultKeyStatistics,summaryDetail,financialData,summaryProfile,price', # Modulos essenciais
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
                modulos = ['defaultKeyStatistics', 'summaryDetail', 'financialData', 'summaryProfile', 'price']
                for mod in modulos:
                    if mod in stock and isinstance(stock[mod], dict):
                        for k in keys_list:
                            val = stock[mod].get(k)
                            if val: return val
                return 0

            # 1. Dados Básicos
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

            # 2. Dados para DCF (Ouro!)
            fcf = self._safe_float(buscar_dado(['freeCashflow', 'freeCashFlow']))
            if fcf == 0:
                # Tentativa de cálculo manual: OCF - CapEx
                ocf = self._safe_float(buscar_dado(['operatingCashflow', 'totalCashFromOperatingActivities']))
                # CapEx costuma não vir explícito em alguns JSONs simplificados, mas tentamos
                # Se não tiver, usamos uma proxy conservadora: EBITDA * 0.5 (Grosseiro mas funcional para fallback)
                ebitda = self._safe_float(buscar_dado(['ebitda']))
                if ocf != 0:
                    fcf = ocf * 0.7 # Assumindo 30% de Capex médio se não tiver dado
                elif ebitda != 0:
                    fcf = ebitda * 0.5 # Proxy conservadora
            
            shares = self._safe_float(buscar_dado(['sharesOutstanding', 'impliedSharesOutstanding']))
            total_debt = self._safe_float(buscar_dado(['totalDebt']))
            total_cash = self._safe_float(buscar_dado(['totalCash', 'totalCashFromOperatingActivities'])) # Cuidado com cash vs OCF
            # Melhor pegar totalCash especifico do balanço
            if total_cash == 0: total_cash = self._safe_float(buscar_dado(['cash']))

            # 3. Valuation & Qualidade
            pl = self._safe_float(buscar_dado(['priceToEarnings', 'trailingPE']))
            lpa = self._safe_float(buscar_dado(['earningsPerShare', 'trailingEps']))
            vpa = self._safe_float(buscar_dado(['bookValuePerShare', 'bookValue']))
            pvp = self._safe_float(buscar_dado(['priceToBook', 'priceToBookRatio']))
            
            divida_ebitda = self._safe_float(buscar_dado(['debtToEbitda']))
            if divida_ebitda == 0 and ebitda > 0: divida_ebitda = total_debt / ebitda
            
            margem_liq = self._safe_float(buscar_dado(['profitMargins', 'profitMargin']))
            
            # Math Fixes
            if vpa == 0 and pvp > 0: vpa = price / pvp
            if pvp == 0 and vpa > 0: pvp = price / vpa
            if lpa == 0 and pl > 0: lpa = price / pl
            if pl == 0 and lpa > 0: pl = price / lpa
            
            # Dividendos
            dy_raw = self._safe_float(buscar_dado(['dividendYield']))
            dy_decimal = dy_raw / 100 if dy_raw > 1 else dy_raw
            
            roe = self._safe_float(buscar_dado(['returnOnEquity']))
            volume = self._safe_float(stock.get('regularMarketVolume'))

            # Graham
            valor_graham = 0
            ms_graham = -100
            if lpa > 0 and vpa > 0:
                valor_graham = np.sqrt(22.5 * lpa * vpa)
                ms_graham = ((valor_graham - price) / price) * 100
            
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
            if divida_ebitda > 5: motivo_trap.append("Dívida Alta")
            if volume < 50000: motivo_trap.append("Iliquidez")
            if motivo_trap: is_trap = True

            return {
                'Logo': logo, 'Ticker': ticker, 'Setor': setor, 'Preço': price,
                'V. Graham': valor_graham, 'MS Graham (%)': ms_graham,
                'DY (%)': dy_decimal * 100, 'P/L': pl, 'P/VP': pvp,
                'ROE (%)': roe * 100, 'Margem Liq (%)': margem_liq * 100,
                'Dívida/EBITDA': divida_ebitda, 'IFR (14)': rsi,
                'FCF': fcf, 'Shares': shares, 'Net Debt': total_debt - total_cash,
                'Armadilha': "⚠️ SIM" if is_trap else "🛡️ NÃO",
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
        if max_p != min_p:
            df['Score Magic'] = 100 * (1 - (df['Magic_Points'] - min_p) / (max_p - min_p))
        else: df['Score Magic'] = 50
        return df.sort_values('Score Magic', ascending=False).fillna(0)

# --- ENGINE DCF ---
def calcular_dcf_individual(row, growth_rate=0.06, wacc=0.12, terminal_growth=0.03, projection_years=5):
    """
    Calcula o Valor Intrínseco via Discounted Cash Flow.
    """
    try:
        fcf = row['FCF']
        shares = row['Shares']
        net_debt = row['Net Debt']
        
        if fcf <= 0 or shares <= 0: return 0, -100 # FCF Negativo não permite DCF simples
        
        # 1. Projeção dos Fluxos de Caixa
        future_fcf = []
        for i in range(1, projection_years + 1):
            fcf_proj = fcf * ((1 + growth_rate) ** i)
            future_fcf.append(fcf_proj)
            
        # 2. Valor Terminal (Perpetuidade)
        # Fórmula: (FCF_final * (1 + g_term)) / (WACC - g_term)
        terminal_value = (future_fcf[-1] * (1 + terminal_growth)) / (wacc - terminal_growth)
        
        # 3. Trazer a Valor Presente (PV)
        pv_flows = 0
        for i, val in enumerate(future_fcf):
            pv_flows += val / ((1 + wacc) ** (i + 1))
            
        pv_terminal = terminal_value / ((1 + wacc) ** projection_years)
        
        # 4. Enterprise Value -> Equity Value
        enterprise_value = pv_flows + pv_terminal
        equity_value = enterprise_value - net_debt
        
        # 5. Valor por Ação
        fair_price = equity_value / shares
        
        # Margem de Segurança
        current_price = row['Preço']
        margin = ((fair_price - current_price) / current_price) * 100
        
        return fair_price, margin
    except:
        return 0, -100

def main():
    st.markdown('<div class="main-header">💎 B3 Pro: Titanium (DCF)</div>', unsafe_allow_html=True)
    
    client = BrapiClient()
    
    # Session State
    if 'dados_b3' not in st.session_state:
        st.session_state['dados_b3'] = pd.DataFrame()

    # SIDEBAR
    st.sidebar.header("⚙️ Controle")
    entrada = st.sidebar.radio("Ativos:", ["Carteira Sugerida", "Minha Lista"])
    
    if entrada == "Carteira Sugerida":
        tickers = client.tickers_padrao
    else:
        text = st.sidebar.text_area("Digite os tickers:", "WEGE3, VALE3, PRIO3")
        if text: tickers = text.split(',')
        else: tickers = []

    # Configurações Globais DCF (Para o Ranking)
    st.sidebar.subheader("📊 Premissas DCF (Ranking)")
    global_wacc = st.sidebar.slider("WACC Global (%)", 8.0, 20.0, 12.0, 0.5) / 100
    global_growth = st.sidebar.slider("Crescimento Global (%)", 0.0, 20.0, 6.0, 0.5) / 100
    
    if st.sidebar.button("🚀 Carregar Dados + Calcular DCF"):
        if not tickers: st.warning("Defina tickers.")
        else:
            with st.spinner("Analisando Fluxo de Caixa e Balanços..."):
                df_new = client.buscar_dados_paralelo(tickers)
                if not df_new.empty:
                    df_new = client.calcular_magic_score(df_new)
                    
                    # Calcula DCF Padrão para todos
                    dcf_results = df_new.apply(
                        lambda x: calcular_dcf_individual(x, growth_rate=global_growth, wacc=global_wacc), 
                        axis=1, result_type='expand'
                    )
                    df_new['V. DCF (Padrão)'] = dcf_results[0]
                    df_new['MS DCF (%)'] = dcf_results[1]
                    
                    st.session_state['dados_b3'] = df_new
                    st.success("Análise Completa!")
                else: st.error("Falha ao buscar dados.")

    st.sidebar.divider()
    
    # FILTROS
    f_armadilha = st.sidebar.checkbox("Ocultar 'Armadilhas'", False)
    
    if not st.session_state['dados_b3'].empty:
        df = st.session_state['dados_b3']
        view = df.copy()
        if f_armadilha: view = view[view['Armadilha'].str.contains("NÃO")]
        
        # TABS
        tab1, tab2, tab3 = st.tabs(["🏆 Ranking Valuation", "🏢 Comparação Setorial", "💎 Valuation DCF Detalhado"])
        
        # --- TAB 1: Ranking ---
        with tab1:
            st.subheader("Melhores Oportunidades (Graham + DCF)")
            st.info(f"O cálculo DCF abaixo usa as premissas globais: Crescimento {global_growth*100}% e WACC {global_wacc*100}%. Para refinar, vá na aba 'Valuation DCF'.")
            
            cols_view = ['Logo', 'Ticker', 'Preço', 'V. Graham', 'V. DCF (Padrão)', 'MS DCF (%)', 'P/L', 'ROE (%)', 'Score Magic']
            st.dataframe(
                view[cols_view],
                column_config={
                    "Logo": st.column_config.ImageColumn("Logo", width="small"),
                    "Preço": st.column_config.NumberColumn(format="R$ %.2f"),
                    "V. Graham": st.column_config.NumberColumn(format="R$ %.2f"),
                    "V. DCF (Padrão)": st.column_config.NumberColumn(format="R$ %.2f"),
                    "MS DCF (%)": st.column_config.NumberColumn(format="%.1f%%"),
                    "Score Magic": st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100),
                },
                hide_index=True, use_container_width=True
            )
        
        # --- TAB 2: Setorial ---
        with tab2:
            st.subheader("Comparação por Setor")
            setores = sorted(view['Setor'].astype(str).unique())
            setor_sel = st.selectbox("Escolha o Setor:", setores)
            df_sec = view[view['Setor'] == setor_sel].sort_values('Score Magic', ascending=False)
            
            if not df_sec.empty:
                media_pl = df_sec['P/L'].mean()
                c1, c2 = st.columns(2)
                c1.metric("Média P/L Setor", f"{media_pl:.1f}x")
                c2.metric("Líder do Setor", df_sec.iloc[0]['Ticker'])
                
                st.dataframe(
                    df_sec[['Ticker', 'Preço', 'MS DCF (%)', 'P/L', 'ROE (%)', 'Dívida/EBITDA']],
                    column_config={"MS DCF (%)": st.column_config.NumberColumn(format="%.1f%%")},
                    hide_index=True, use_container_width=True
                )
        
        # --- TAB 3: DCF DETALHADO (A JOIA DA COROA) ---
        with tab3:
            st.subheader("🔬 Calculadora DCF Profissional")
            
            # Seletor de Ativo
            ticker_dcf = st.selectbox("Selecione o Ativo para Valuation:", view['Ticker'].unique())
            row = view[view['Ticker'] == ticker_dcf].iloc[0]
            
            col_input, col_result = st.columns([1, 2])
            
            with col_input:
                st.markdown("#### Premissas do Modelo")
                dcf_growth = st.slider("Crescimento (5 anos) %", 0.0, 25.0, global_growth*100, 0.5) / 100
                dcf_wacc = st.slider("WACC (Taxa de Desconto) %", 8.0, 25.0, global_wacc*100, 0.5) / 100
                dcf_terminal = st.slider("Crescimento Perpétuo %", 0.0, 6.0, 3.0, 0.1) / 100
                
                # Dados da Empresa
                st.markdown("#### Dados Financeiros")
                st.text_input("Ticker", row['Ticker'], disabled=True)
                st.number_input("Fluxo Caixa Livre (FCF) Milhões", value=float(row['FCF']/1e6), disabled=True)
                st.number_input("Dívida Líquida Milhões", value=float(row['Net Debt']/1e6), disabled=True)
            
            with col_result:
                # Recalcula com inputs do usuário
                fair_price, margin = calcular_dcf_individual(row, dcf_growth, dcf_wacc, dcf_terminal)
                
                st.markdown("### 🎯 Resultado do Valuation")
                
                k1, k2, k3 = st.columns(3)
                k1.metric("Preço Atual", f"R$ {row['Preço']:.2f}")
                k2.metric("Preço Justo (DCF)", f"R$ {fair_price:.2f}")
                k3.metric("Upside / Downside", f"{margin:.1f}%", delta_color="normal" if margin > 0 else "off")
                
                if fair_price <= 0:
                    st.error("⚠️ O cálculo retornou valor negativo ou zero. Verifique se o Fluxo de Caixa Livre (FCF) é positivo.")
                else:
                    if margin > 20: st.success("✅ Oportunidade: Margem de Segurança Alta")
                    elif margin > 0: st.info("⚖️ Preço Justo (Leve Desconto)")
                    else: st.warning("⛔ Ativo Caro segundo estas premissas")

                st.divider()
                
                # --- MATRIZ DE SENSIBILIDADE (HEATMAP) ---
                st.markdown("#### 🔥 Matriz de Sensibilidade (Preço Justo)")
                
                # Gera faixas de WACC e Growth
                wacc_range = [dcf_wacc - 0.02, dcf_wacc - 0.01, dcf_wacc, dcf_wacc + 0.01, dcf_wacc + 0.02]
                growth_range = [dcf_growth - 0.02, dcf_growth - 0.01, dcf_growth, dcf_growth + 0.01, dcf_growth + 0.02]
                
                z_values = []
                for w in wacc_range:
                    row_z = []
                    for g in growth_range:
                        fp, _ = calcular_dcf_individual(row, g, w, dcf_terminal)
                        row_z.append(round(fp, 2))
                    z_values.append(row_z)
                
                # Plot Heatmap
                fig_heat = px.imshow(
                    z_values,
                    labels=dict(x="Crescimento (Growth)", y="WACC", color="Preço Justo"),
                    x=[f"{g*100:.1f}%" for g in growth_range],
                    y=[f"{w*100:.1f}%" for w in wacc_range],
                    text_auto=True,
                    color_continuous_scale='RdYlGn'
                )
                fig_heat.update_layout(height=400)
                st.plotly_chart(fig_heat, use_container_width=True)
                st.caption("Eixo X: Taxa de Crescimento | Eixo Y: Taxa de Desconto (WACC)")

    else:
        st.info("👈 Clique em 'Carregar Dados' para iniciar.")

if __name__ == "__main__":
    main()
