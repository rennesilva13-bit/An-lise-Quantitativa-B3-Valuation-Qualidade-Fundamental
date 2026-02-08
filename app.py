"""
B3 Pro Analyzer - Sapphire Edition (State Persistence Fix)
==========================================================
Correção de UX:
- Implementação de Session State para manter os dados na tela
  quando o usuário interage com filtros ou abas.
- O botão agora serve para "Atualizar Dados".
- Filtros aplicados em tempo real sem precisar recarregar a API.

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
</style>
""", unsafe_allow_html=True)

class BrapiClient:
    def __init__(self):
        self.token = "rxNx6YXRYuEkQFDAc66r3C"
        self.base_url = "https://brapi.dev/api"
        
        self.tickers_padrao = [
            'BBAS3', 'ITUB4', 'BBDC4', 'SANB11', 'ABCB4', 'BRSR6', # Bancos
            'TAEE11', 'TRPL4', 'CPLE6', 'EGIE3', 'ALUP11', 'CMIG4', # Elétricas
            'VALE3', 'CSNA3', 'GGBR4', 'USIM5', 'GOAU4', # Siderurgia
            'WEGE3', 'PSSA3', 'BBSE3', 'CXSE3', # Industrial/Seguros
            'SAPR11', 'CSMG3', 'SBSP3', # Saneamento
            'PRIO3', 'PETR4', 'RECV3', # Petróleo
            'JBSS3', 'MRFG3', 'BEEF3', # Frigoríficos
            'MGLU3', 'LREN3', 'RDOR3' # Varejo/Saúde
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
            'modules': 'defaultKeyStatistics,summaryDetail,financialData,summaryProfile,price',
            'range': '1mo',
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

            price = self._safe_float(stock.get('regularMarketPrice'))
            if price == 0: return None
            
            logo = stock.get('logourl', 'https://brapi.dev/favicon.ico')
            
            setor = stock.get('summaryProfile', {}).get('sector', 'Outros')
            if not setor: setor = "Outros"
            
            setor_map = {
                'Financial Services': 'Financeiro', 'Utilities': 'Utilidades Púb.',
                'Basic Materials': 'Materiais Básicos', 'Energy': 'Energia',
                'Industrials': 'Industrial', 'Consumer Defensive': 'Consumo N. Cíclico',
                'Consumer Cyclical': 'Consumo Cíclico', 'Technology': 'Tecnologia',
                'Healthcare': 'Saúde', 'Real Estate': 'Imobiliário'
            }
            setor = setor_map.get(setor, setor)

            pl = self._safe_float(buscar_dado(['priceToEarnings', 'trailingPE']))
            lpa = self._safe_float(buscar_dado(['earningsPerShare', 'trailingEps']))
            vpa = self._safe_float(buscar_dado(['bookValuePerShare', 'bookValue']))
            pvp = self._safe_float(buscar_dado(['priceToBook', 'priceToBookRatio']))
            
            divida_ebitda = self._safe_float(buscar_dado(['debtToEbitda']))
            if divida_ebitda == 0:
                total_debt = self._safe_float(buscar_dado(['totalDebt']))
                ebitda = self._safe_float(buscar_dado(['ebitda']))
                if ebitda > 0: divida_ebitda = total_debt / ebitda
            
            margem_liq = self._safe_float(buscar_dado(['profitMargins', 'profitMargin']))
            
            if vpa == 0 and pvp > 0: vpa = price / pvp
            if pvp == 0 and vpa > 0: pvp = price / vpa
            if lpa == 0 and pl > 0: lpa = price / pl
            if pl == 0 and lpa > 0: pl = price / lpa
                
            dy_raw = self._safe_float(buscar_dado(['dividendYield']))
            dy_decimal = dy_raw / 100 if dy_raw > 1 else dy_raw
            
            roe = self._safe_float(buscar_dado(['returnOnEquity']))
            volume = self._safe_float(stock.get('regularMarketVolume'))
            
            valor_graham = 0
            ms_graham = -100
            if lpa > 0 and vpa > 0:
                valor_graham = np.sqrt(22.5 * lpa * vpa)
                ms_graham = ((valor_graham - price) / price) * 100
            
            rsi = 50
            hist = stock.get('historicalDataPrice', [])
            if hist:
                closes = [d.get('close') for d in hist if d.get('close')]
                rsi = self.calcular_rsi(closes)
            
            motivo_trap = []
            is_trap = False
            if roe != 0 and roe < 0.05: motivo_trap.append("ROE Baixo")
            if divida_ebitda > 5: motivo_trap.append("Dívida Alta")
            if margem_liq != 0 and margem_liq < 0.03: motivo_trap.append("Margem Baixa")
            if volume < 50000: motivo_trap.append("Iliquidez")
            if motivo_trap: is_trap = True

            return {
                'Logo': logo, 'Ticker': ticker, 'Setor': setor, 'Preço': price,
                'V. Graham': valor_graham, 'MS Graham (%)': ms_graham,
                'DY (%)': dy_decimal * 100, 'P/L': pl, 'P/VP': pvp,
                'ROE (%)': roe * 100, 'Margem Liq (%)': margem_liq * 100,
                'Dívida/EBITDA': divida_ebitda, 'IFR (14)': rsi,
                'Armadilha': "⚠️ SIM" if is_trap else "🛡️ NÃO",
                'Alertas': ", ".join(motivo_trap) if motivo_trap else "OK",
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

def main():
    st.markdown('<div class="main-header">💎 B3 Pro: Sapphire Edition</div>', unsafe_allow_html=True)
    
    client = BrapiClient()
    
    # --- GERENCIAMENTO DE ESTADO (MEMÓRIA) ---
    if 'dados_b3' not in st.session_state:
        st.session_state['dados_b3'] = pd.DataFrame()

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ Controle")
    entrada = st.sidebar.radio("Ativos:", ["Carteira Sugerida", "Minha Lista"])
    
    if entrada == "Carteira Sugerida":
        tickers = client.tickers_padrao
        st.sidebar.info(f"Monitorando {len(tickers)} ativos.")
    else:
        text = st.sidebar.text_area("Digite os tickers:", "PETR4, VALE3, WEGE3")
        if text: tickers = text.split(',')
        else: tickers = []

    # Botão de Carregamento (Só precisa clicar uma vez)
    if st.sidebar.button("🚀 Carregar / Atualizar Dados"):
        if not tickers:
            st.warning("Defina tickers.")
        else:
            with st.spinner("Baixando dados da B3..."):
                df_new = client.buscar_dados_paralelo(tickers)
                if not df_new.empty:
                    df_new = client.calcular_magic_score(df_new)
                    st.session_state['dados_b3'] = df_new
                    st.success("Dados atualizados com sucesso!")
                else:
                    st.error("Falha ao buscar dados.")

    st.sidebar.divider()
    
    # --- FILTROS EM TEMPO REAL ---
    # (Estes filtros funcionam instantaneamente se os dados já estiverem na memória)
    f_armadilha = st.sidebar.checkbox("Ocultar 'Armadilhas'", False)
    min_ms = st.sidebar.slider("Margem Graham Mínima %", -100, 100, -100)
    
    # --- VISUALIZAÇÃO ---
    # Verifica se existe dado na memória
    if not st.session_state['dados_b3'].empty:
        df = st.session_state['dados_b3']
        
        # Aplica filtros na memória local (rápido)
        view = df.copy()
        if f_armadilha: view = view[view['Armadilha'].str.contains("NÃO")]
        view = view[view['MS Graham (%)'] >= min_ms]
        
        # TABS
        tab1, tab2 = st.tabs(["🏆 Ranking Geral", "🏢 Comparação Setorial"])
        
        # ABA 1
        with tab1:
            st.subheader(f"Visão Consolidada ({len(view)})")
            cols_view = ['Logo', 'Ticker', 'Setor', 'Preço', 'MS Graham (%)', 'P/L', 'ROE (%)', 'Dívida/EBITDA', 'Score Magic']
            st.dataframe(
                view[cols_view],
                column_config={
                    "Logo": st.column_config.ImageColumn("Logo", width="small"),
                    "Preço": st.column_config.NumberColumn(format="R$ %.2f"),
                    "MS Graham (%)": st.column_config.NumberColumn(format="%.1f%%"),
                    "Dívida/EBITDA": st.column_config.NumberColumn(format="%.2f"),
                    "Score Magic": st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100),
                    "ROE (%)": st.column_config.NumberColumn(format="%.1f%%"),
                },
                hide_index=True, use_container_width=True
            )
            csv = view.drop(columns=['Logo']).to_csv(index=False).encode('utf-8')
            st.download_button("📥 Baixar CSV", csv, 'b3_analise.csv', 'text/csv')

        # ABA 2
        with tab2:
            st.subheader("Comparação Setorial 🍎")
            if not view.empty:
                setores = sorted(view['Setor'].astype(str).unique())
                
                # Seleção de Setor (Agora não apaga mais a tela!)
                setor_sel = st.selectbox("Escolha o Setor:", setores)
                
                df_sec = view[view['Setor'] == setor_sel].sort_values('Score Magic', ascending=False)
                
                if not df_sec.empty:
                    media_pl = df_sec['P/L'].mean()
                    media_roe = df_sec['ROE (%)'].mean()
                    media_dy = df_sec['DY (%)'].mean()
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Média P/L Setor", f"{media_pl:.1f}x")
                    c2.metric("Média ROE Setor", f"{media_roe:.1f}%")
                    c3.metric("Média DY Setor", f"{media_dy:.1f}%")
                    
                    st.divider()
                    col_radar, col_scatter = st.columns([1, 1])
                    
                    with col_radar:
                        st.markdown("#### 🕸️ Raio-X")
                        empresa_comp = st.selectbox("Comparar Empresa:", df_sec['Ticker'].unique())
                        if empresa_comp:
                            row = df_sec[df_sec['Ticker'] == empresa_comp].iloc[0]
                            categories = ['ROE (%)', 'Margem Liq (%)', 'DY (%)']
                            val_empresa = [row['ROE (%)'], row['Margem Liq (%)'], row['DY (%)']]
                            val_media = [media_roe, df_sec['Margem Liq (%)'].mean(), media_dy]
                            
                            fig_radar = go.Figure()
                            fig_radar.add_trace(go.Scatterpolar(r=val_empresa, theta=categories, fill='toself', name=empresa_comp))
                            fig_radar.add_trace(go.Scatterpolar(r=val_media, theta=categories, fill='toself', name='Média Setor', opacity=0.5))
                            fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True)), height=400)
                            st.plotly_chart(fig_radar, use_container_width=True)

                    with col_scatter:
                        st.markdown("#### 🎯 Posicionamento")
                        fig_s = px.scatter(
                            df_sec, x='P/L', y='ROE (%)',
                            size='Preço', text='Ticker', color='Score Magic',
                            labels={'P/L': 'P/L (Barato →)', 'ROE (%)': 'ROE (Qualidade ↑)'},
                            color_continuous_scale='RdYlGn', height=400
                        )
                        fig_s.update_traces(textposition='top center')
                        st.plotly_chart(fig_s, use_container_width=True)
                else:
                    st.info("Nenhuma empresa encontrada neste setor.")
    else:
        st.info("👈 Clique em 'Carregar / Atualizar Dados' na barra lateral para começar.")

if __name__ == "__main__":
    main()
