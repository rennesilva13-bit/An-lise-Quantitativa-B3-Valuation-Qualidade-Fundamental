"""
B3 Quant Analyzer - Value Investing & Valuation
===============================================
Aplicação Streamlit para análise fundamentalista.
Correções aplicadas:
1. CSS forçando texto preto nos cards (visível no Dark Mode).
2. Limpeza de aspas na entrada de tickers.
3. Tratamento de erros de conexão.

Autor: Analista Quantitativo
Data: 2026
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
import warnings

# Ignorar avisos
warnings.filterwarnings('ignore')

# --- Configuração da Página ---
st.set_page_config(
    page_title="B3 Value Investing",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS Customizado (Correção Definitiva de Cores) ---
st.markdown("""
<style>
    /* Título Principal */
    .main-header { 
        font-size: 2rem; 
        font-weight: bold; 
        color: #0066cc; 
        text-align: center; 
        margin-bottom: 1rem; 
    }
    
    /* ESTILO DOS CARTÕES (METRICS) */
    /* Força o fundo cinza claro e texto preto, ignorando o tema escuro do usuário */
    div[data-testid="stMetric"] {
        background-color: #f0f2f6 !important;
        border-radius: 10px;
        padding: 15px;
        border-left: 5px solid #0066cc;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    
    /* Título do Cartão (Label) */
    div[data-testid="stMetric"] label {
        color: #333333 !important; /* Cinza escuro */
        font-weight: 600 !important;
    }
    
    /* Valor do Cartão (Número Grande) */
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #000000 !important; /* Preto absoluto */
        font-weight: bold !important;
    }
    
    /* Delta (Percentual pequeno) */
    div[data-testid="stMetricDelta"] {
        font-weight: bold !important;
    }
</style>
""", unsafe_allow_html=True)

class B3Fundamentalist:
    """Motor de análise focado em Valuation e Segurança."""
    
    def __init__(self):
        self.tickers_padrao = [
            'BBAS3', 'ITUB4', 'BBDC4', 'SANB11',
            'TAEE11', 'TRPL4', 'CPLE6', 'EGIE3',
            'VALE3', 'CSNA3', 'GGBR4', 'WEGE3', 
            'PSSA3', 'BBSE3', 'CXSE3', 'SAPR11'
        ]

    def _tratar_ticker(self, ticker):
        """Limpa o ticker e garante o sufixo .SA"""
        # Remove aspas simples e duplas, espaços e converte para maiúsculo
        ticker = ticker.replace("'", "").replace('"', "").strip().upper()
        if not ticker.endswith('.SA'):
            return f"{ticker}.SA"
        return ticker

    def calcular_valor_graham(self, lpa, vpa):
        if lpa > 0 and vpa > 0:
            return np.sqrt(22.5 * lpa * vpa)
        return 0

    def calcular_valor_bazin(self, dividendos_12m):
        if dividendos_12m > 0:
            return dividendos_12m / 0.06
        return 0

    @st.cache_data(ttl=3600)
    def buscar_dados(_self, tickers):
        dados_lista = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        total = len(tickers)
        
        for i, ticker_raw in enumerate(tickers):
            ticker = _self._tratar_ticker(ticker_raw)
            status_text.text(f"Analisando: {ticker} ({i+1}/{total})")
            
            try:
                stock = yf.Ticker(ticker)
                
                # Tenta pegar preço rápido
                try:
                    price = stock.fast_info.last_price
                except:
                    hist = stock.history(period="1d")
                    if not hist.empty:
                        price = hist['Close'].iloc[-1]
                    else:
                        continue 

                info = stock.info
                
                # Coleta segura de dados (evitando None)
                lpa = info.get('trailingEps', 0) or 0
                vpa = info.get('bookValue', 0) or 0
                roe = info.get('returnOnEquity', 0) or 0
                divida_ebitda = info.get('debtToEbitda', 0) or 0
                margem_liq = info.get('profitMargins', 0) or 0
                dy_rate = info.get('dividendRate', 0) or 0
                dy_percent = info.get('dividendYield', 0) or 0
                volume = info.get('averageVolume', 0) or 0
                pl = info.get('trailingPE', 0) or 0
                
                # Cálculos
                valor_graham = _self.calcular_valor_graham(lpa, vpa)
                valor_bazin = _self.calcular_valor_bazin(dy_rate)
                
                if valor_graham > 0:
                    ms_graham = ((valor_graham - price) / price) * 100
                else:
                    ms_graham = -100
                
                # Detecção de Armadilhas
                is_trap = False
                motivo_trap = []
                
                if roe < 0.05: motivo_trap.append("ROE Baixo")
                if divida_ebitda > 4: motivo_trap.append("Dívida Alta")
                if margem_liq < 0.03: motivo_trap.append("Margem Baixa")
                if volume < 500000: motivo_trap.append("Liquidez Baixa")
                
                if motivo_trap: is_trap = True

                dados_lista.append({
                    'Ticker': ticker.replace('.SA', ''),
                    'Preço Atual': price,
                    'Valor Graham': valor_graham,
                    'Valor Bazin': valor_bazin,
                    'MS Graham (%)': ms_graham,
                    'DY (%)': dy_percent * 100,
                    'P/L': pl,
                    'ROE (%)': roe * 100,
                    'Dívida/EBITDA': divida_ebitda,
                    'Armadilha': "⚠️ SIM" if is_trap else "🛡️ NÃO",
                    'Alertas': ", ".join(motivo_trap) if motivo_trap else "OK",
                    'Score Magic': 0
                })
                
            except Exception:
                pass
                
            progress_bar.progress((i + 1) / total)
            
        progress_bar.empty()
        status_text.empty()
        
        return pd.DataFrame(dados_lista)

    def calcular_magic_score(self, df):
        if df.empty: return df
        df = df.copy()
        
        mask_validos = df['P/L'] > 0
        if not mask_validos.any(): return df

        df.loc[mask_validos, 'Rank_PL'] = df.loc[mask_validos, 'P/L'].rank(ascending=True)
        df.loc[mask_validos, 'Rank_ROE'] = df.loc[mask_validos, 'ROE (%)'].rank(ascending=False)
        df['Magic_Points'] = df['Rank_PL'] + df['Rank_ROE']
        
        min_pts = df['Magic_Points'].min()
        max_pts = df['Magic_Points'].max()
        
        if max_pts != min_pts:
            df['Score Magic'] = 100 * (1 - (df['Magic_Points'] - min_pts) / (max_pts - min_pts))
        else:
            df['Score Magic'] = 50
            
        df['Score Magic'] = df['Score Magic'].fillna(0)
        return df.sort_values('Score Magic', ascending=False)

def main():
    st.markdown('<div class="main-header">💎 B3 Quant Analyzer: Value Investing</div>', unsafe_allow_html=True)
    analyzer = B3Fundamentalist()
    
    st.sidebar.header("🔍 Configuração")
    modo_input = st.sidebar.radio("Ativos:", ["Lista Padrão", "Minha Carteira"])
    
    if modo_input == "Lista Padrão":
        tickers_selecionados = analyzer.tickers_padrao
        st.sidebar.info(f"{len(tickers_selecionados)} ativos selecionados.")
    else:
        # Input corrigido para aceitar aspas e espaços
        lista_texto = st.sidebar.text_area("Cole os tickers:", "WEGE3, ITUB4, VALE3")
        if lista_texto:
            import re
            # Remove aspas antes de processar
            lista_limpa = lista_texto.replace('"', '').replace("'", "")
            tickers_selecionados = re.split(r'[,\s;]+', lista_limpa)
            tickers_selecionados = [t for t in tickers_selecionados if t]
        else:
            tickers_selecionados = []

    st.sidebar.markdown("---")
    filtrar_armadilhas = st.sidebar.checkbox("Esconder 'Armadilhas'", value=True)
    ms_minima = st.sidebar.slider("Margem de Segurança Mínima %", -50, 100, 0)
    
    if st.sidebar.button("🚀 Processar Valuation"):
        if not tickers_selecionados:
            st.warning("Insira pelo menos um ticker.")
            return

        df = analyzer.buscar_dados(tickers_selecionados)
        
        if df.empty:
            st.error("❌ Nenhum dado encontrado. Verifique se os códigos estão corretos (ex: PETR4, VALE3).")
            return

        df = analyzer.calcular_magic_score(df)
        
        df_display = df.copy()
        if filtrar_armadilhas:
            df_display = df_display[df_display['Armadilha'].str.contains("NÃO")]
            
        df_display = df_display[df_display['MS Graham (%)'] >= ms_minima]

        # --- Dashboard ---
        st.subheader("🏆 Top Oportunidades")
        
        cols_view = ['Ticker', 'Preço Atual', 'Valor Graham', 'Valor Bazin', 'MS Graham (%)', 'DY (%)', 'ROE (%)', 'Score Magic', 'Alertas']
        
        st.dataframe(
            df_display[cols_view].style.format({
                'Preço Atual': 'R$ {:.2f}', 'Valor Graham': 'R$ {:.2f}', 'Valor Bazin': 'R$ {:.2f}',
                'MS Graham (%)': '{:.1f}%', 'DY (%)': '{:.1f}%', 'ROE (%)': '{:.1f}%', 'Score Magic': '{:.0f}'
            }).background_gradient(cmap='Greens', subset=['MS Graham (%)', 'Score Magic']),
            use_container_width=True, height=400
        )

        st.markdown("---")
        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader("📊 Matriz de Qualidade")
            fig = px.scatter(
                df_display, x='MS Graham (%)', y='ROE (%)', size='DY (%)', color='Score Magic',
                hover_name='Ticker', height=500, color_continuous_scale='RdYlGn'
            )
            fig.add_vline(x=0, line_dash="dot", annotation_text="Preço Justo")
            st.plotly_chart(fig, use_container_width=True)
            
        with col2:
            st.info("Quanto mais à direita e ao alto, melhor (Mais barata e mais rentável).")

        st.markdown("---")
        st.subheader("🔍 Raio-X do Ativo")
        if not df_display.empty:
            ticker_select = st.selectbox("Detalhar Ativo:", df_display['Ticker'].unique())
            row = df_display[df_display['Ticker'] == ticker_select].iloc[0]
            
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Preço Atual", f"R$ {row['Preço Atual']:.2f}")
                st.metric("Valor Justo (Graham)", f"R$ {row['Valor Graham']:.2f}", f"{row['MS Graham (%)']:.1f}%")
            with c2:
                st.metric("Dividend Yield", f"{row['DY (%)']:.1f}%")
                st.metric("Teto Bazin", f"R$ {row['Valor Bazin']:.2f}")
            with c3:
                st.metric("ROE", f"{row['ROE (%)']:.1f}%")
                st.metric("Dívida/EBITDA", f"{row['Dívida/EBITDA']:.2f}")

            if row['Alertas'] != "OK":
                st.error(f"🚨 Alerta: {row['Alertas']}")
            else:
                st.success("✅ Fundamentos Sólidos")

if __name__ == "__main__":
    main()
