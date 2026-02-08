"""
B3 Quant Analyzer 2.0 - Value Investing & Valuation
===================================================
Aplicação Streamlit para análise fundamentalista e cálculo de valor intrínseco.
Foco: Longo prazo, Dividendos e Segurança (Graham & Bazin).

Autor: Analista Quantitativo
Data: 2026
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import warnings

warnings.filterwarnings('ignore')

# Configuração da página
st.set_page_config(
    page_title="B3 Value Investing",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS Customizado ---
st.markdown("""
<style>
    .main-header { font-size: 2rem; font-weight: bold; color: #0066cc; text-align: center; margin-bottom: 1rem; }
    .stMetric { background-color: #f8f9fa; padding: 10px; border-radius: 5px; border-left: 5px solid #0066cc; }
    .success-text { color: green; font-weight: bold; }
    .danger-text { color: red; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

class B3Fundamentalist:
    """
    Motor de análise focado em Valuation e Segurança.
    """
    
    def __init__(self):
        # Tickers padrão para facilitar o uso inicial
        self.tickers_padrao = [
            'BBAS3', 'ITUB4', 'BBDC4', 'SANB11', # Bancos
            'TAEE11', 'TRPL4', 'CPLE6', 'EGIE3', # Elétricas
            'VALE3', 'CSNA3', 'GGBR4',           # Commodities
            'WEGE3', 'PSSA3', 'BBSE3', 'CXSE3'   # Outros
        ]

    def _tratar_ticker(self, ticker):
        """Garante que o ticker tenha o sufixo .SA"""
        ticker = ticker.strip().upper()
        if not ticker.endswith('.SA'):
            return f"{ticker}.SA"
        return ticker

    def calcular_valor_graham(self, lpa, vpa):
        """
        Fórmula de Benjamin Graham: Raiz(22.5 * LPA * VPA)
        Retorna o Preço Justo.
        """
        if lpa > 0 and vpa > 0:
            return np.sqrt(22.5 * lpa * vpa)
        return 0

    def calcular_valor_bazin(self, dividendos_12m):
        """
        Método de Décio Bazin: Preço Justo = Dividendos Anuais / 6%
        """
        if dividendos_12m > 0:
            return dividendos_12m / 0.06
        return 0

    @st.cache_data(ttl=3600) # Cache de 1 hora para não ficar lento
    def buscar_dados(_self, tickers):
        """
        Busca dados fundamentalistas e calcula indicadores avançados.
        Usa cache do Streamlit para performance.
        """
        dados_lista = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        total = len(tickers)
        
        for i, ticker_raw in enumerate(tickers):
            ticker = _self._tratar_ticker(ticker_raw)
            status_text.text(f"Analisando fundamentos: {ticker}... ({i+1}/{total})")
            
            try:
                stock = yf.Ticker(ticker)
                # Fast_info costuma ser mais rápido e confiável para preços atuais
                price = stock.fast_info.last_price
                
                # Tenta pegar info completa
                info = stock.info
                
                # Dados Essenciais (com tratamento de erro/zeros)
                lpa = info.get('trailingEps', 0) or 0
                vpa = info.get('bookValue', 0) or 0
                roe = info.get('returnOnEquity', 0) or 0
                divida_ebitda = info.get('debtToEbitda', 0) or 0
                margem_liq = info.get('profitMargins', 0) or 0
                dy_rate = info.get('dividendRate', 0) or 0  # Em valor monetário
                dy_percent = info.get('dividendYield', 0) or 0
                volume = info.get('averageVolume', 0) or 0
                
                # Cálculos de Valuation
                valor_graham = _self.calcular_valor_graham(lpa, vpa)
                valor_bazin = _self.calcular_valor_bazin(dy_rate)
                
                # Margem de Segurança (Graham)
                ms_graham = ((valor_graham - price) / price) * 100 if valor_graham > 0 else -100
                
                # Classificação de "Armadilha"
                # Critérios: Prejuízo, Dívida alta ou Sem liquidez
                is_trap = False
                motivo_trap = []
                
                if roe < 0.05: # ROE menor que 5% (ou negativo)
                    is_trap = True
                    motivo_trap.append("Baixa Rentabilidade")
                if divida_ebitda > 4: # Alavancagem alta
                    is_trap = True
                    motivo_trap.append("Dívida Alta")
                if margem_liq < 0.03: # Margem líquida < 3%
                    is_trap = True
                    motivo_trap.append("Margem Baixa")
                if volume < 500000: # Liquidez < 500k/dia
                    is_trap = True
                    motivo_trap.append("Baixa Liquidez")

                dados_lista.append({
                    'Ticker': ticker.replace('.SA', ''),
                    'Preço Atual': price,
                    'Valor Graham': valor_graham,
                    'Valor Bazin': valor_bazin,
                    'MS Graham (%)': ms_graham,
                    'DY (%)': dy_percent * 100,
                    'P/L': info.get('trailingPE', 0),
                    'P/VP': info.get('priceToBook', 0),
                    'ROE (%)': roe * 100,
                    'Margem Liq. (%)': margem_liq * 100,
                    'Dívida/EBITDA': divida_ebitda,
                    'Armadilha': "⚠️ SIM" if is_trap else "🛡️ NÃO",
                    'Alertas': ", ".join(motivo_trap) if motivo_trap else "OK",
                    'Score Magic': 0 # Será calculado depois
                })
                
            except Exception as e:
                # Opcional: print(f"Erro em {ticker}: {e}")
                pass
                
            progress_bar.progress((i + 1) / total)
            
        progress_bar.empty()
        status_text.empty()
        
        return pd.DataFrame(dados_lista)

    def calcular_magic_score(self, df):
        """
        Implementa uma versão simplificada da Magic Formula (Greenblatt):
        Ranking combinado de Earning Yield (barato) + ROE (qualidade).
        """
        if df.empty: return df
        
        df = df.copy()
        
        # Remover empresas com LPA negativo para o ranking
        df_valid = df[df['P/L'] > 0]
        
        # Ranking de Preço (Earning Yield: Maior P/L invertido é melhor, ou seja, Menor P/L)
        df['Rank_PL'] = df['P/L'].rank(ascending=True)
        
        # Ranking de Qualidade (Maior ROE é melhor)
        df['Rank_ROE'] = df['ROE (%)'].rank(ascending=False)
        
        # Score Final (Menor soma é melhor)
        df['Magic_Points'] = df['Rank_PL'] + df['Rank_ROE']
        
        # Normalizar para visualização (0 a 100, onde 100 é o melhor)
        max_pts = df['Magic_Points'].max()
        min_pts = df['Magic_Points'].min()
        
        if max_pts != min_pts:
            df['Score Magic'] = 100 * (1 - (df['Magic_Points'] - min_pts) / (max_pts - min_pts))
        else:
            df['Score Magic'] = 50
            
        return df.sort_values('Score Magic', ascending=False)

def main():
    st.markdown('<div class="main-header">💎 B3 Quant Analyzer: Value Investing</div>', unsafe_allow_html=True)
    
    analyzer = B3Fundamentalist()
    
    # --- Sidebar ---
    st.sidebar.header("🔍 Configuração da Análise")
    
    # Input de Tickers
    modo_input = st.sidebar.radio("Seleção de Ativos:", ["Lista Padrão (Sugestão)", "Minha Carteira / Lista Personalizada"])
    
    if modo_input == "Lista Padrão (Sugestão)":
        tickers_selecionados = analyzer.tickers_padrao
        st.sidebar.info(f"{len(tickers_selecionados)} ativos selecionados.")
    else:
        lista_texto = st.sidebar.text_area("Cole os tickers (separados por vírgula ou espaço):", "WEGE3, ITSA4, FLRY3, LEVE3")
        if lista_texto:
            import re
            tickers_selecionados = re.split(r'[,\s;]+', lista_texto)
            tickers_selecionados = [t for t in tickers_selecionados if t] # Remove vazios
        else:
            tickers_selecionados = []

    # Filtros Globais
    st.sidebar.markdown("---")
    st.sidebar.subheader("🛡️ Filtros de Segurança")
    filtrar_armadilhas = st.sidebar.checkbox("Esconder 'Armadilhas' (Dívida Alta/Prejuízo)", value=True)
    ms_minima = st.sidebar.slider("Margem de Segurança Mínima (Graham) %", -50, 100, 0)
    
    if st.sidebar.button("🚀 Processar Valuation"):
        if not tickers_selecionados:
            st.warning("Por favor, insira pelo menos um ticker.")
            return

        # Busca e Processamento
        df = analyzer.buscar_dados(tickers_selecionados)
        
        if df.empty:
            st.error("Não foi possível coletar dados. Verifique os tickers.")
            return

        # Aplica Magic Score
        df = analyzer.calcular_magic_score(df)
        
        # Aplica Filtros Visuais
        if filtrar_armadilhas:
            df_display = df[df['Armadilha'].str.contains("NÃO")]
        else:
            df_display = df
            
        df_display = df_display[df_display['MS Graham (%)'] >= ms_minima]

        # --- Dashboard ---
        
        # 1. Top Picks
        st.subheader("🏆 Top Oportunidades (Ranking Magic Score)")
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.markdown("Combinação de **Qualidade (ROE)** e **Preço Baixo (P/L)**.")
            cols_view = ['Ticker', 'Preço Atual', 'Valor Graham', 'Valor Bazin', 'MS Graham (%)', 'DY (%)', 'ROE (%)', 'Score Magic', 'Alertas']
            
            st.dataframe(
                df_display[cols_view].style.format({
                    'Preço Atual': 'R$ {:.2f}',
                    'Valor Graham': 'R$ {:.2f}',
                    'Valor Bazin': 'R$ {:.2f}',
                    'MS Graham (%)': '{:.1f}%',
                    'DY (%)': '{:.1f}%',
                    'ROE (%)': '{:.1f}%',
                    'Score Magic': '{:.0f}'
                }).background_gradient(cmap='Greens', subset=['MS Graham (%)', 'Score Magic']),
                use_container_width=True,
                height=400
            )
            
        with col2:
            st.info("""
            **Legenda:**
            
            🧠 **Valor Graham:** Preço justo baseado em Lucro e Patrimônio.
            
            💰 **Valor Bazin:** Preço teto para receber 6% de dividendos.
            
            🛡️ **MS (Margem de Segurança):** O desconto atual em relação ao preço de Graham.
            
            ✨ **Score Magic:** Nota de 0 a 100 combinando rentabilidade e preço.
            """)

        # 2. Gráfico de Quadrantes (Risco x Retorno)
        st.markdown("---")
        st.subheader("📊 Matriz de Valor: Qualidade vs. Desconto")
        
        fig = px.scatter(
            df_display,
            x='MS Graham (%)',
            y='ROE (%)',
            size='DY (%)',
            color='Score Magic',
            hover_name='Ticker',
            hover_data=['Preço Atual', 'Valor Graham', 'Alertas'],
            title='Onde estão as Joias? (Canto Superior Direito = Melhor)',
            labels={'MS Graham (%)': 'Desconto (Margem de Segurança)', 'ROE (%)': 'Qualidade (ROE)'},
            height=600,
            color_continuous_scale='RdYlGn'
        )
        
        # Linhas de referência
        fig.add_hline(y=15, line_dash="dot", annotation_text="ROE Excelente (>15%)")
        fig.add_vline(x=0, line_dash="dot", annotation_text="Preço Justo Graham")
        fig.add_vline(x=30, line_dash="dash", line_color="green", annotation_text="Zona de Oportunidade (>30%)")
        
        st.plotly_chart(fig, use_container_width=True)

        # 3. Análise Individual Detalhada
        st.markdown("---")
        st.subheader("🔍 Raio-X do Ativo")
        ticker_select = st.selectbox("Escolha um ativo para ver detalhes:", df['Ticker'].unique())
        
        row = df[df['Ticker'] == ticker_select].iloc[0]
        
        col_a, col_b, col_c = st.columns(3)
        
        with col_a:
            st.metric("Preço Atual", f"R$ {row['Preço Atual']:.2f}")
            dif_graham = row['MS Graham (%)']
            st.metric("Potencial (Graham)", f"{dif_graham:.1f}%", delta_color="normal" if dif_graham > 0 else "inverse")
            
        with col_b:
            st.metric("Preço Teto Bazin (6%)", f"R$ {row['Valor Bazin']:.2f}")
            st.metric("Dividend Yield", f"{row['DY (%)']:.1f}%")
            
        with col_c:
            st.metric("ROE (Rentabilidade)", f"{row['ROE (%)']:.1f}%")
            divida_status = "✅ Controlada" if row['Dívida/EBITDA'] < 3 else "⚠️ Alta"
            st.metric("Dívida/EBITDA", f"{row['Dívida/EBITDA']:.2f}", divida_status)
            
        if row['Alertas'] != "OK":
            st.error(f"🚨 Pontos de Atenção: {row['Alertas']}")
        else:
            st.success("✅ Aparentemente sem 'armadilhas' fundamentais óbvias.")

if __name__ == "__main__":
    main()
