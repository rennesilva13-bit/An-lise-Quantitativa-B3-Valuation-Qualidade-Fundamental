"""
B3 Dividend Pro - Anti-Trap Edition
===================================
Foco: Renda Passiva Sustentável.
Filtros Anti-Armadilha:
1. Payout Ratio (Evita empresas queimando caixa).
2. Lucro Recorrente (Evita empresas com prejuízo).
3. Liquidez Mínima.
4. Magic Dividend Score (Yield + Segurança).

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
        background-color: #f0fff4 !important; /* Verde bem claro */
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
    
    /* Destaque para Alertas */
    .trap-alert {
        color: #721c24;
        background-color: #f8d7da;
        border-color: #f5c6cb;
        padding: 10px;
        border-radius: 5px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

class BrapiClient:
    def __init__(self):
        self.token = "rxNx6YXRYuEkQFDAc66r3C"
        self.base_url = "https://brapi.dev/api"
        
        # Lista de Dividendos (Setores perenes: Bancos, Elétricas, Seguros, Saneamento)
        self.tickers_padrao = [
            'BBAS3', 'ITUB4', 'BBDC4', 'SANB11', 'ABCB4', 'BRSR6', # Bancos
            'TAEE11', 'TRPL4', 'CPLE6', 'EGIE3', 'ALUP11', 'CMIG4', 'AURE3', # Elétricas
            'BBSE3', 'CXSE3', 'PSSA3', # Seguros
            'SAPR11', 'CSMG3', 'SBSP3', # Saneamento
            'VALE3', 'CSNA3', 'GGBR4', # Commodities (Cíclicas mas pagam bem)
            'PETR4', 'PRIO3', # Petróleo
            'LEVE3', 'TUPY3', 'UNIP6' # Industriais pagadoras
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
        
        # Módulos focados em Dividendos e Balanço
        params = {
            'fundamental': 'true', 
            'dividends': 'true',
            'modules': 'summaryDetail,defaultKeyStatistics,financialData,summaryProfile,price',
            'range': '1y', # Histórico curto para validar preço
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

            # Extração de Dados
            price = self._safe_float(stock.get('regularMarketPrice'))
            if price == 0: return None
            
            logo = stock.get('logourl', 'https://brapi.dev/favicon.ico')
            setor = stock.get('summaryProfile', {}).get('sector', 'Outros')
            
            # --- DADOS DE DIVIDENDOS ---
            dy_raw = self._safe_float(buscar_dado(['dividendYield', 'trailingAnnualDividendYield']))
            # Normalização: Brapi as vezes manda 0.06 (6%) ou 6.0 (6%)
            dy_percent = dy_raw * 100 if dy_raw < 1 else dy_raw
            
            # Payout Ratio (Quanto do lucro é distribuído)
            # Ideal: Entre 25% e 90%. Acima de 100% é insustentável (exceto FIIs).
            payout = self._safe_float(buscar_dado(['payoutRatio']))
            payout_percent = payout * 100 if payout < 2 else payout # Proteção contra dados estranhos
            
            # Lucratividade
            lpa = self._safe_float(buscar_dado(['earningsPerShare', 'trailingEps']))
            pl = self._safe_float(buscar_dado(['priceToEarnings', 'trailingPE']))
            
            # Solvência (Segurança do Dividendo)
            divida_ebitda = self._safe_float(buscar_dado(['debtToEbitda']))
            
            # Histórico de Proventos (Últimos 12m em R$)
            dividend_rate = self._safe_float(buscar_dado(['dividendRate', 'trailingAnnualDividendRate']))
            
            # --- DETECTOR DE ARMADILHA (TRAP) ---
            is_trap = False
            warnings_list = []
            
            # 1. Armadilha de Payout (Distribui mais que lucra)
            if payout_percent > 110: 
                is_trap = True
                warnings_list.append(f"Payout Explosivo ({payout_percent:.0f}%)")
            
            # 2. Armadilha de Prejuízo (Pagou dividendo queimando caixa ou dívida)
            if lpa < 0:
                is_trap = True
                warnings_list.append("Empresa no Prejuízo")
                
            # 3. Armadilha de Yield Excessivo (Suspeita de não recorrente ou crash)
            if dy_percent > 25:
                warnings_list.append("Yield Anormal (>25%) - Verifique Recorrência")
                # Não marca como Trap fatal, mas avisa
            
            # 4. Armadilha de Yield Zero
            if dy_percent < 0.1:
                warnings_list.append("Não paga dividendos")
                
            # 5. Dívida Perigosa
            if divida_ebitda > 4.5:
                warnings_list.append("Dívida Alta (Risco Corte)")

            return {
                'Logo': logo, 'Ticker': ticker, 'Setor': setor, 'Preço': price,
                'DY (%)': dy_percent,
                'Payout (%)': payout_percent,
                'Div. 12m (R$)': dividend_rate,
                'P/L': pl, 'LPA': lpa, 'Dívida/EBITDA': divida_ebitda,
                'Is Trap': is_trap,
                'Status': "⚠️ CUIDADO" if is_trap else ("🚨 ALERTA" if warnings_list else "✅ SEGURO"),
                'Motivo': ", ".join(warnings_list) if warnings_list else "Sustentável",
                'Score Div': 0 # Calculado depois
            }
        except: return None

    def buscar_dados_paralelo(self, tickers_list):
        tickers_clean = [self._tratar_ticker(t) for t in tickers_list if t.strip()]
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(self.buscar_ativo_individual, tickers_clean))
        return pd.DataFrame([r for r in results if r is not None])

    def calcular_dividend_score(self, df):
        """
        Score focado em Dividendos:
        - 40% Yield
        - 40% Sustentabilidade (Payout controlado + Lucro)
        - 20% Saúde Financeira (Dívida baixa)
        """
        if df.empty: return df
        df = df.copy()
        
        # Filtra apenas empresas viáveis para o ranking
        mask = (df['DY (%)'] > 0) & (df['Payout (%)'] > 0) & (df['Payout (%)'] < 200)
        if not mask.any(): 
            df['Score Div'] = 0
            return df
            
        # 1. Score Yield (Quanto maior melhor, até certo ponto)
        # Limitamos o "melhor yield" em 18% para não premiar traps
        df['Yield_Capped'] = df['DY (%)'].clip(upper=18)
        df.loc[mask, 'Rank_Yield'] = df.loc[mask, 'Yield_Capped'].rank(ascending=True)
        
        # 2. Score Sustentabilidade (Payout ideal entre 40% e 80%)
        # Criamos uma métrica de distância do Payout ideal (60%)
        df['Dist_Payout'] = abs(df['Payout (%)'] - 60)
        df.loc[mask, 'Rank_Payout'] = df['Dist_Payout'].rank(ascending=False) # Menor distância é melhor
        
        # 3. Score Segurança (Menor Dívida é melhor)
        df.loc[mask, 'Rank_Divida'] = df.loc[mask, 'Dívida/EBITDA'].rank(ascending=False)
        
        # Peso Final
        df['Raw_Score'] = (df['Rank_Yield']*2) + (df['Rank_Payout']*1.5) + (df['Rank_Divida']*1)
        
        # Normalização 0-100
        min_p, max_p = df['Raw_Score'].min(), df['Raw_Score'].max()
        if max_p != min_p:
            df['Score Div'] = 100 * (df['Raw_Score'] - min_p) / (max_p - min_p)
        else: df['Score Div'] = 50
        
        return df.sort_values('Score Div', ascending=False).fillna(0)

def main():
    st.markdown('<div class="main-header">💰 B3 Dividend Pro: Anti-Trap</div>', unsafe_allow_html=True)
    
    client = BrapiClient()
    
    # Session State
    if 'dados_div' not in st.session_state:
        st.session_state['dados_div'] = pd.DataFrame()

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ Carteira")
    entrada = st.sidebar.radio("Ativos:", ["Carteira 'Vacas Leiteiras' (Sugerida)", "Minha Carteira"])
    
    if entrada == "Carteira 'Vacas Leiteiras' (Sugerida)":
        tickers = client.tickers_padrao
        st.sidebar.info(f"Analisando {len(tickers)} pagadoras de dividendos.")
    else:
        text = st.sidebar.text_area("Digite os tickers:", "TAEE11, BBSE3, ITSA4")
        if text: tickers = text.split(',')
        else: tickers = []

    if st.sidebar.button("🔄 Atualizar Dados de Proventos"):
        if not tickers: st.warning("Defina tickers.")
        else:
            with st.spinner("Analisando sustentabilidade dos dividendos..."):
                df_new = client.buscar_dados_paralelo(tickers)
                if not df_new.empty:
                    df_new = client.calcular_dividend_score(df_new)
                    st.session_state['dados_div'] = df_new
                    st.success("Análise Concluída!")
                else: st.error("Erro ao buscar dados.")

    st.sidebar.divider()
    
    # --- FILTROS ANTI-TRAP ---
    st.sidebar.subheader("🛡️ Filtros Anti-Trap")
    
    f_trap = st.sidebar.checkbox("Ocultar 'Traps' Confirmadas", value=True, help="Remove empresas com Payout > 110% ou Prejuízo.")
    
    min_dy = st.sidebar.slider("Dividend Yield Mínimo (%)", 0.0, 15.0, 6.0, help="Filtra empresas que pagam pouco.")
    max_payout = st.sidebar.slider("Payout Máximo Aceitável (%)", 50, 200, 100, help="Acima de 100% a empresa está pagando mais do que lucra (insustentável).")
    
    # --- VISUALIZAÇÃO ---
    if not st.session_state['dados_div'].empty:
        df = st.session_state['dados_div']
        
        # Aplicação dos Filtros
        view = df.copy()
        
        if f_trap:
            view = view[view['Is Trap'] == False]
        
        view = view[
            (view['DY (%)'] >= min_dy) & 
            (view['Payout (%)'] <= max_payout)
        ]
        
        # KPIs
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Média Yield Carteira", f"{view['DY (%)'].mean():.1f}%")
        c2.metric("Payout Médio", f"{view['Payout (%)'].mean():.1f}%")
        c3.metric("Ativos Seguros", f"{len(view)}")
        c4.metric("Traps Identificadas", f"{len(df) - len(view)}", delta_color="inverse")
        
        st.divider()

        # TABS
        tab1, tab2 = st.tabs(["🏆 Ranking Dividendos", "🔎 Análise de Sustentabilidade"])
        
        with tab1:
            st.subheader("Top Pagadoras Sustentáveis")
            
            # Formatação condicional para Status
            st.dataframe(
                view[['Logo', 'Ticker', 'Preço', 'DY (%)', 'Payout (%)', 'Div. 12m (R$)', 'Status', 'Motivo', 'Score Div']],
                column_config={
                    "Logo": st.column_config.ImageColumn("Logo", width="small"),
                    "Preço": st.column_config.NumberColumn(format="R$ %.2f"),
                    "DY (%)": st.column_config.NumberColumn(format="%.1f%%"),
                    "Payout (%)": st.column_config.NumberColumn(format="%.0f%%"),
                    "Div. 12m (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Score Div": st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100),
                },
                hide_index=True, use_container_width=True
            )
            
            st.info("💡 **Score Div:** Premia empresas com Yield alto, mas penaliza fortemente Payout explosivo e Dívida alta.")

        with tab2:
            st.subheader("Matriz Anti-Trap: Yield vs Payout")
            
            col_chart, col_legenda = st.columns([3, 1])
            
            with col_chart:
                # Scatter Plot: DY vs Payout
                # O ideal é Quadrante Inferior Direito (DY Alto, Payout Baixo/Médio)
                fig = px.scatter(
                    view, x='Payout (%)', y='DY (%)',
                    size='Score Div', color='Status',
                    hover_name='Ticker',
                    text='Ticker',
                    title="Onde estão as oportunidades reais?",
                    color_discrete_map={"✅ SEGURO": "green", "⚠️ CUIDADO": "red", "🚨 ALERTA": "orange"},
                    height=500
                )
                
                # Zonas de Risco
                fig.add_vrect(x0=100, x1=200, fillcolor="red", opacity=0.1, annotation_text="Payout Insustentável")
                fig.add_shape(type="line", x0=0, y0=6, x1=max_payout, y1=6, line=dict(color="green", width=1, dash="dot"))
                
                fig.update_traces(textposition='top center')
                st.plotly_chart(fig, use_container_width=True)
                
            with col_legenda:
                st.markdown("""
                **Como ler este gráfico:**
                
                🟢 **Área Segura:** Payout abaixo de 90-100% e Yield acima de 6%.
                
                🔴 **Zona de Perigo:** Payout acima de 100% (Direita). A empresa está queimando caixa para pagar você.
                
                ⚪ **Bola Pequena:** Score baixo (Dívida alta ou lucro instável).
                """)

            # Tabela de Traps (O que foi filtrado)
            st.subheader("🗑️ Lixeira (Ativos Reprovados nos Filtros)")
            reprovadas = df[~df['Ticker'].isin(view['Ticker'])]
            if not reprovadas.empty:
                st.dataframe(
                    reprovadas[['Ticker', 'DY (%)', 'Payout (%)', 'Motivo']],
                    column_config={
                        "DY (%)": st.column_config.NumberColumn(format="%.1f%%"),
                        "Payout (%)": st.column_config.NumberColumn(format="%.0f%%"),
                    },
                    hide_index=True, use_container_width=True
                )
            else:
                st.success("Nenhuma trap encontrada na lista atual!")

    else:
        st.info("👈 Clique em 'Atualizar Dados' para começar a análise de renda.")

if __name__ == "__main__":
    main()
