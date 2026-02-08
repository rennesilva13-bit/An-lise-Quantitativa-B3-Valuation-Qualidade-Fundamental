"""
B3 Quant Analyzer - Análise Quantitativa de Ações da B3
=======================================================
Aplicação Streamlit para identificação de oportunidades com base em
valuation atrativo e qualidade fundamental.

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
    page_title="B3 Quant Analyzer",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo CSS personalizado
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
    }
    .stButton>button {
        width: 100%;
        background-color: #1f77b4;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

class B3QuantAnalyzer:
    def __init__(self):
        # Mapeamento aproximado de setores (baseado em prefixos comuns dos tickers)
        self.setores_map = {
            'AURE': 'Energia',
            'CMIG': 'Energia',
            'CPFE': 'Energia',
            'CPLE': 'Energia',
            'EGIE': 'Energia',
            'ELET': 'Energia',
            'ENGI': 'Energia',
            'ENEV': 'Energia',
            'ENMT': 'Energia',
            'EQTL': 'Energia',
            'TAEE': 'Energia',
            'TRPL': 'Energia',
            'AESB': 'Energia',
            'ALUP': 'Energia',
            'CEEB': 'Energia',
            'CLSC': 'Energia',
            'COCE': 'Energia',
            'GEPA': 'Energia',
            'LIGT': 'Energia',
            'NEOE': 'Energia',
            'RNEW': 'Energia',
            'OUTROS': 'Outros'
        }
        
        # Lista padrão fornecida pelo usuário
        self.tickers_padrao = [
            "AURE3", "CMIG3", "CMIG4", "CPFE3", "CPLE3", "CPLE6", "EGIE3",
            "ELET3", "ELET6", "ENGI11", "ENEV3", "ENMT3", "EQTL3", "TAEE11",
            "TRPL4", "AESB3", "ALUP11", "CEEB3", "CLSC3", "COCE5", "GEPA4",
            "LIGT3", "NEOE3", "RNEW11"
        ]
        
        # Pesos para cálculo do score
        self.pesos = {'valuation': 0.5, 'qualidade': 0.5}
    
    def buscar_dados_fundamentalistas(self, ticker):
        try:
            stock = yf.Ticker(f"{ticker}.SA")  # Adiciona .SA automaticamente
            info = stock.info
            
            pl = info.get('trailingPE', np.nan)
            pvp = info.get('priceToBook', np.nan)
            ev_ebitda = info.get('enterpriseToEbitda', np.nan)
            dy = info.get('dividendYield', np.nan)
            if not np.isnan(dy): dy *= 100
            
            roe = info.get('returnOnEquity', np.nan)
            if not np.isnan(roe): roe *= 100
            
            margem_ebit = info.get('ebitdaMargins', np.nan)
            if not np.isnan(margem_ebit): margem_ebit *= 100
            
            div_liq_ebitda = info.get('debtToEbitda', np.nan) or info.get('totalDebtToEBITDA', np.nan)
            
            preco_atual = info.get('currentPrice', np.nan)
            receita_crescimento = info.get('revenueGrowth', np.nan)
            if not np.isnan(receita_crescimento): receita_crescimento *= 100
            
            # Determina setor aproximado pelo ticker
            prefixo = ticker[:4]
            setor = self.setores_map.get(prefixo, 'OUTROS')
            
            return {
                'ticker': ticker,
                'nome': info.get('longName', ticker),
                'setor': setor,
                'preco': preco_atual,
                'pl': pl,
                'pvp': pvp,
                'ev_ebitda': ev_ebitda,
                'dy': dy,
                'roe': roe,
                'margem_ebit': margem_ebit,
                'div_liq_ebitda': div_liq_ebitda,
                'crescimento_receita': receita_crescimento
            }
        except Exception as e:
            st.warning(f"Erro ao obter dados de {ticker}: {str(e)}")
            return None
    
    def carregar_dados_batch(self, tickers):
        dados_lista = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, ticker in enumerate(tickers):
            status_text.text(f"Processando {ticker} ({i+1}/{len(tickers)})")
            dados = self.buscar_dados_fundamentalistas(ticker)
            if dados:
                dados_lista.append(dados)
            progress_bar.progress((i + 1) / len(tickers))
        
        status_text.empty()
        return pd.DataFrame(dados_lista)
    
    def calcular_scores(self, df):
        if df.empty:
            return df
        
        # Normalização (maior = melhor)
        df['pl_score'] = 1 / (df['pl'].replace([np.nan, np.inf], 100) + 1)
        df['pvp_score'] = 1 / (df['pvp'].replace([np.nan, np.inf], 100) + 1)
        df['ev_ebitda_score'] = 1 / (df['ev_ebitda'].replace([np.nan, np.inf], 100) + 1)
        df['dy_score'] = df['dy'].fillna(0) / 20  # normaliza DY
        df['roe_score'] = df['roe'].fillna(0) / 50
        df['margem_score'] = df['margem_ebit'].fillna(0) / 50
        df['div_liq_score'] = 1 / (df['div_liq_ebitda'].abs().replace([np.nan, np.inf], 10) + 1)
        df['cresc_score'] = df['crescimento_receita'].fillna(0) / 50
        
        df['score_valuation'] = df[['pl_score', 'pvp_score', 'ev_ebitda_score', 'dy_score']].mean(axis=1)
        df['score_qualidade'] = df[['roe_score', 'margem_score', 'div_liq_score', 'cresc_score']].mean(axis=1)
        
        df['score_final'] = (
            df['score_valuation'] * self.pesos['valuation'] +
            df['score_qualidade'] * self.pesos['qualidade']
        )
        
        def classificar(score):
            if pd.isna(score): return "Indisponível"
            if score >= 0.70: return "Excelente"
            if score >= 0.50: return "Boa"
            if score >= 0.30: return "Média"
            return "Baixa"
        
        df['classificacao'] = df['score_final'].apply(classificar)
        return df.sort_values('score_final', ascending=False)

def main():
    st.markdown('<h1 class="main-header">B3 Quant Analyzer – Setor Elétrico</h1>', unsafe_allow_html=True)
    st.markdown("Análise quantitativa focada em empresas do setor elétrico da B3")

    analyzer = B3QuantAnalyzer()

    # Barra lateral – Configuração dos tickers
    with st.sidebar:
        st.header("Configuração da Análise")
        
        tickers_input = st.text_area(
            "Insira os tickers (um por linha, sem .SA)",
            value="\n".join(analyzer.tickers_padrao),
            height=300,
            help="Exemplo:\nAURE3\nCMIG3\nTAEE11\n..."
        )
        
        tickers = [t.strip().upper() for t in tickers_input.split("\n") if t.strip()]
        
        st.subheader("Filtros Adicionais")
        min_roe = st.slider("ROE mínimo (%)", 0.0, 50.0, 8.0)
        max_div_ebitda = st.slider("Dívida Líquida/EBITDA máxima", 0.0, 6.0, 4.0)
        max_pl = st.slider("P/L máximo", 5.0, 40.0, 20.0)
        min_dy = st.slider("Dividend Yield mínimo (%)", 0.0, 15.0, 5.0)
        
        if st.button("Executar Análise", type="primary"):
            if not tickers:
                st.error("Nenhum ticker informado.")
                return
            
            with st.spinner("Obtendo dados da B3..."):
                df_raw = analyzer.carregar_dados_batch(tickers)
            
            if df_raw.empty:
                st.error("Nenhum dado válido retornado. Verifique os tickers ou conexão.")
                return
            
            df = analyzer.calcular_scores(df_raw)
            
            # Aplicar filtros
            df_filtrado = df[
                (df['roe'] >= min_roe) &
                (df['div_liq_ebitda'] <= max_div_ebitda) &
                (df['pl'] <= max_pl) &
                (df['dy'] >= min_dy)
            ].copy()
            
            st.session_state['df_completo'] = df
            st.session_state['df_filtrado'] = df_filtrado
            st.success(f"Análise finalizada. {len(df_filtrado)} ações atendem aos critérios.")

    # Área principal
    if 'df_filtrado' in st.session_state and not st.session_state['df_filtrado'].empty:
        df_filtrado = st.session_state['df_filtrado']
        df_completo = st.session_state['df_completo']
        
        tab1, tab2, tab3 = st.tabs(["Dashboard", "Detalhes", "Dados Completos"])
        
        with tab1:
            st.subheader("Top Oportunidades (Setor Elétrico)")
            st.dataframe(
                df_filtrado[['ticker', 'nome', 'setor', 'preco', 'pl', 'dy', 'roe', 'score_final', 'classificacao']]
                .head(15)
                .round(2)
            )
            
            fig = px.scatter(
                df_filtrado,
                x='pl',
                y='roe',
                size='dy',
                color='score_final',
                hover_name='ticker',
                title="P/L vs ROE (tamanho = DY)",
                labels={'pl': 'P/L', 'roe': 'ROE (%)', 'dy': 'DY (%)'}
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with tab2:
            ticker_sel = st.selectbox("Selecione uma ação", df_filtrado['ticker'].tolist())
            if ticker_sel:
                row = df_filtrado[df_filtrado['ticker'] == ticker_sel].iloc[0]
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**{row['nome']}** ({row['ticker']})")
                    st.write(f"Setor: {row['setor']}")
                    st.write(f"Preço: R$ {row['preco']:.2f}")
                    st.write(f"Score Final: **{row['score_final']:.2f}** – {row['classificacao']}")
                    st.write("**Valuation**")
                    st.write(f"P/L: {row['pl']:.1f}")
                    st.write(f"P/VP: {row['pvp']:.1f}")
                    st.write(f"DY: {row['dy']:.1f}%")
                
                with col2:
                    st.write("**Qualidade**")
                    st.write(f"ROE: {row['roe']:.1f}%")
                    st.write(f"Margem EBIT: {row['margem_ebit']:.1f}%")
                    st.write(f"Dív. Líq./EBITDA: {row['div_liq_ebitda']:.1f}")
        
        with tab3:
            st.subheader("Dados Completos")
            st.dataframe(df_filtrado.round(2))
            
            csv = df_filtrado.to_csv(index=False).encode('utf-8')
            st.download_button("Baixar CSV", csv, "analise_setor_eletrico.csv", "text/csv")
    
    else:
        st.info("Insira os tickers na barra lateral e clique em 'Executar Análise' para iniciar.")

if __name__ == "__main__":
    main()
