"""
B3 Pro Analyzer - Diamond Edition (Final)
=========================================
Correções e Funcionalidades:
1. FIX Dívida/EBITDA: Calcula manualmente (Dívida Total / EBITDA) se o campo direto falhar.
2. Comparação Setorial: Abas separadas para análise Apple-to-Apple.
3. Robustez: Mantém a engenharia reversa de VPA e P/L.

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
        
        # Lista expandida para ter diversidade de setores
        self.tickers_padrao = [
            'BBAS3', 'ITUB4', 'BBDC4', 'SANB11', 'ABCB4', 'BRSR6', # Bancos
            'TAEE11', 'TRPL4', 'CPLE6', 'EGIE3', 'ALUP11', 'CMIG4', # Elétricas
            'VALE3', 'CSNA3', 'GGBR4', 'USIM5', 'GOAU4', # Siderurgia/Mineração
            'WEGE3', 'PSSA3', 'BBSE3', 'CXSE3', # Bens Ind / Seguros
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
        
        # Módulos essenciais
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
            
            if 'results' not in data or not data['results']:
                return None
            
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

            # --- Extração ---
            price = self._safe_float(stock.get('regularMarketPrice'))
            if price == 0: return None
            
            logo = stock.get('logourl', 'https://brapi.dev/favicon.ico')
            
            # SETOR
            setor = stock.get('summaryProfile', {}).get('sector', 'Outros')
            if not setor: setor = "Outros"
            
            # Tradução Setores
            setor_map = {
                'Financial Services': 'Financeiro', 'Utilities': 'Utilidades Púb.',
                'Basic Materials': 'Materiais Básicos', 'Energy': 'Energia',
                'Industrials': 'Industrial', 'Consumer Defensive': 'Consumo N. Cíclico',
                'Consumer Cyclical': 'Consumo Cíclico', 'Technology': 'Tecnologia',
                'Healthcare': 'Saúde', 'Real Estate': 'Imobiliário'
            }
            setor = setor_map.get(setor, setor)

            # Valuation
            pl = self._safe_float(buscar_dado(['priceToEarnings', 'trailingPE']))
            lpa = self._safe_float(buscar_dado(['earningsPerShare', 'trailingEps']))
            vpa = self._safe_float(buscar_dado(['bookValuePerShare', 'bookValue']))
            pvp = self._safe_float(buscar_dado(['priceToBook', 'priceToBookRatio']))
            
            # Solvência - CORREÇÃO MANUAL
            divida_ebitda = self._safe_float(buscar_dado(['debtToEbitda']))
            
            # Se a API não der o Debt/EBITDA pronto, calculamos na unha
            if divida_ebitda == 0:
                total_debt = self._safe_float(buscar_dado(['totalDebt']))
                ebitda = self._safe_float(buscar_dado(['ebitda']))
                if ebitda > 0:
                    divida_ebitda = total_debt / ebitda
            
            margem_liq = self._safe_float(buscar_dado(['profitMargins', 'profitMargin']))
            
            # Math Fix (Engenharia Reversa de Valuation)
            if vpa == 0 and pvp > 0: vpa = price / pvp
            if pvp == 0 and vpa > 0: pvp = price / vpa
            if lpa == 0 and pl > 0: lpa = price / pl
            if pl == 0 and lpa > 0: pl = price / lpa
                
            dy_raw = self._safe_float(buscar_dado(['dividendYield']))
            dy_decimal = dy_raw / 100 if dy_raw > 1 else dy_raw
            
            roe = self._safe_float(buscar_dado(['returnOnEquity']))
            volume = self._safe_float(stock.get('regularMarketVolume'))
            
            # Cálculos
            valor_graham = 0
            ms_graham = -100
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
            
            # Armadilhas
            motivo_trap = []
            is_trap = False
            if roe != 0 and roe < 0.05: motivo_trap.append("ROE Baixo (<5%)")
            
            # Tolerância maior para dívida (alguns setores operam alavancados)
            if divida_ebitda > 5: motivo_trap.append("Dívida Crítica (>5x)")
            
            if margem_liq != 0 and margem_liq < 0.03: motivo_trap.append("Margem Baixa (<3%)")
            if volume < 50000: motivo_trap.append("Sem Liquidez")
            if motivo_trap: is_trap = True

            return {
                'Logo': logo,
                'Ticker': ticker,
                'Setor': setor,
                'Preço': price,
                'V. Graham': valor_graham,
                'MS Graham (%)': ms_graham,
                'DY (%)': dy_decimal * 100,
                'P/L': pl,
                'P/VP': pvp,
                'ROE (%)': roe * 100,
                'Margem Liq (%)': margem_liq * 100,
                'Dívida/EBITDA': divida_ebitda,
                'IFR (14)': rsi,
                'Armadilha': "⚠️ SIM" if is_trap else "🛡️ NÃO",
                'Alertas': ", ".join(motivo_trap) if motivo_trap else "OK",
                'Score Magic': 0
            }

        except Exception as e:
            return None

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
        else:
            df['Score Magic'] = 50
        return df.sort_values('Score Magic', ascending=False).fillna(0)

def main():
    st.markdown('<div class="main-header">💎 B3 Pro: Diamond Edition</div>', unsafe_allow_html=True)
    
    client = BrapiClient()
    
    # --- SIDEBAR ---
    st.sidebar.header("⚙️ Controle")
    entrada = st.sidebar.radio("Ativos:", ["Carteira Sugerida (Diversificada)", "Minha Lista"])
    
    if entrada == "Carteira Sugerida (Diversificada)":
        tickers = client.tickers_padrao
        st.sidebar.info(f"Monitorando {len(tickers)} ativos de {len(set(client.tickers_padrao))} setores.")
    else:
        text = st.sidebar.text_area("Digite os tickers:", "PETR4, VALE3, WEGE3, PRIO3, CMIG4")
        if text: tickers = text.split(',')
        else: tickers = []

    st.sidebar.divider()
    f_armadilha = st.sidebar.checkbox("Ocultar 'Armadilhas'", False)
    min_ms = st.sidebar.slider("Margem Graham Mínima %", -100, 100, -100)
    
    if st.sidebar.button("🚀 Processar Análise"):
        if not tickers:
            st.warning("Defina tickers.")
            return
            
        with st.spinner(f"Analisando {len(tickers)} ativos (Calculando Dívida Real + Setores)..."):
            df = client.buscar_dados_paralelo(tickers)
        
        if df.empty:
            st.error("Nenhum dado encontrado.")
            return

        df = client.calcular_magic_score(df)
        
        # Filtros Globais
        view = df.copy()
        if f_armadilha: view = view[view['Armadilha'].str.contains("NÃO")]
        view = view[view['MS Graham (%)'] >= min_ms]

        # --- SISTEMA DE ABAS ---
        tab1, tab2 = st.tabs(["🏆 Ranking Geral", "🏢 Comparação Setorial"])
        
        # --- ABA 1: GERAL ---
        with tab1:
            st.subheader(f"Visão Consolidada ({len(view)} ativos)")
            
            # Adicionei Setor na visualização
            cols_view = ['Logo', 'Ticker', 'Setor', 'Preço', 'V. Graham', 'MS Graham (%)', 'P/L', 'Dívida/EBITDA', 'Score Magic']
            
            st.dataframe(
                view[cols_view],
                column_config={
                    "Logo": st.column_config.ImageColumn("Logo", width="small"),
                    "Preço": st.column_config.NumberColumn(format="R$ %.2f"),
                    "V. Graham": st.column_config.NumberColumn(format="R$ %.2f"),
                    "MS Graham (%)": st.column_config.NumberColumn(format="%.1f%%"),
                    "Dívida/EBITDA": st.column_config.NumberColumn(format="%.2f"), # Agora vai aparecer!
                    "Score Magic": st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100),
                },
                hide_index=True,
                use_container_width=True
            )
            
            # Botão Download Global
            csv = view.drop(columns=['Logo']).to_csv(index=False).encode('utf-8')
            st.download_button("📥 Baixar Relatório Completo (CSV)", csv, 'b3_diamond.csv', 'text/csv')

            st.info("Nota sobre Bancos (BBAS3, ITUB4, etc): É normal a Dívida/EBITDA ser 0.00, pois bancos não usam EBITDA na contabilidade padrão.")

        # --- ABA 2: SETORIAL (Apple-to-Apple) ---
        with tab2:
            st.subheader("Análise Setorial 🍎")
            
            if not view.empty:
                setores_disponiveis = sorted(view['Setor'].astype(str).unique())
                setor_sel = st.selectbox("Selecione o Setor:", setores_disponiveis)
                
                # Filtra apenas o setor
                df_sector = view[view['Setor'] == setor_sel].sort_values('Score Magic', ascending=False)
                
                if not df_sector.empty:
                    # Métricas do Setor (Benchmark)
                    media_pl = df_sector['P/L'].mean()
                    media_roe = df_sector['ROE (%)'].mean()
                    media_dy = df_sector['DY (%)'].mean()
                    
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Média P/L do Setor", f"{media_pl:.1f}x")
                    col2.metric("Média ROE do Setor", f"{media_roe:.1f}%")
                    col3.metric("Média DY do Setor", f"{media_dy:.1f}%")
                    
                    st.markdown("---")
                    
                    # Gráfico Comparativo
                    col_g1, col_g2 = st.columns([2, 1])
                    
                    with col_g1:
                        st.markdown("#### 🥇 Ranking do Setor")
                        fig_bar = px.bar(
                            df_sector, 
                            x='Score Magic', 
                            y='Ticker', 
                            orientation='h',
                            color='Dívida/EBITDA', # Cor agora indica risco de dívida
                            text='Score Magic',
                            color_continuous_scale='RdYlGn_r', # Vermelho se dívida alta
                            hover_data=['Preço', 'P/L', 'ROE (%)']
                        )
                        fig_bar.update_traces(texttemplate='%{text:.0f}', textposition='outside')
                        fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
                        st.plotly_chart(fig_bar, use_container_width=True)
                    
                    with col_g2:
                        st.markdown("#### 🔬 Tabela Setorial")
                        st.dataframe(
                            df_sector[['Ticker', 'P/L', 'ROE (%)', 'Dívida/EBITDA']],
                            column_config={
                                 "P/L": st.column_config.NumberColumn(format="%.1f"),
                                 "ROE (%)": st.column_config.NumberColumn(format="%.1f%%"),
                                 "Dívida/EBITDA": st.column_config.NumberColumn(format="%.2f"),
                            },
                            hide_index=True,
                            use_container_width=True
                        )
                else:
                    st.warning("Nenhuma ação deste setor passou nos seus filtros de segurança.")

if __name__ == "__main__":
    main()
