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
from plotly.subplots import make_subplots
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
    """
    Classe principal para análise quantitativa de ações da B3.
    Implementa metodologia de dois pilares: Valuation + Qualidade Fundamental.
    """
    
    def __init__(self):
        # Mapeamento de setores B3 (simplificado)
        self.setores_map = {
            'FINL': 'Financeiro',
            'UTILS': 'Utilidades',
            'CONS_DUR': 'Consumo Cíclico',
            'CONS_STAP': 'Consumo Não Cíclico',
            'SAUDE': 'Saúde',
            'TECN': 'Tecnologia',
            'INDS': 'Industrial',
            'MATR': 'Materiais Básicos',
            'COMM': 'Comunicações',
            'ENER': 'Energia',
            'OUTROS': 'Outros'
        }
        
        # Lista de tickers de exemplo (expanda conforme necessário)
        self.tickers_exemplo = [
            'ITUB4.SA', 'BBDC4.SA', 'SANB11.SA', 'TAEE11.SA', 'SBSP3.SA',
            'MGLU3.SA', 'LREN3.SA', 'VIVT3.SA', 'PETR4.SA', 'VALE3.SA',
            'CSNA3.SA', 'GOLL4.SA', 'EMBR3.SA', 'RADL3.SA', 'JBSS3.SA',
            'HAPV3.SA', 'QUAL3.SA'
        ]
        
        # Pesos para cálculo do score
        self.pesos = {
            'valuation': 0.5,
            'qualidade': 0.5
        }
    
    def buscar_dados_fundamentalistas(self, ticker):
        """
        Busca dados fundamentalistas usando yfinance.
        Retorna dicionário com métricas principais ou None em caso de erro.
        """
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Métricas de Valuation
            pl = info.get('trailingPE', np.nan)
            pvp = info.get('priceToBook', np.nan)
            ev_ebitda = info.get('enterpriseToEbitda', np.nan)
            dy = info.get('dividendYield', np.nan)
            if not np.isnan(dy):
                dy *= 100  # para %
            
            # Métricas de Qualidade
            roe = info.get('returnOnEquity', np.nan)
            if not np.isnan(roe):
                roe *= 100
            
            margem_ebit = info.get('ebitdaMargins', np.nan)
            if not np.isnan(margem_ebit):
                margem_ebit *= 100
            
            div_liq_ebitda = info.get('debtToEbitda', np.nan)  # ou 'totalDebtToEBITDA' em algumas versões
            
            # Dados de preço e outros
            preco_atual = info.get('currentPrice', np.nan)
            preco_52w_high = info.get('fiftyTwoWeekHigh', np.nan)
            preco_52w_low = info.get('fiftyTwoWeekLow', np.nan)
            receita_crescimento = info.get('revenueGrowth', np.nan)
            if not np.isnan(receita_crescimento):
                receita_crescimento *= 100
            
            return {
                'ticker': ticker.replace('.SA', ''),
                'nome': info.get('longName', ticker),
                'setor': self.setores_map.get(ticker[:4], 'OUTROS'),  # mapeamento aproximado
                'preco': preco_atual,
                'pl': pl,
                'pvp': pvp,
                'ev_ebitda': ev_ebitda,
                'dy': dy,
                'roe': roe,
                'margem_ebit': margem_ebit,
                'div_liq_ebitda': div_liq_ebitda,
                'crescimento_receita': receita_crescimento,
                'preco_52w_high': preco_52w_high,
                'preco_52w_low': preco_52w_low,
                'volume_medio': info.get('averageVolume', np.nan)
            }
        except Exception as e:
            st.warning(f"Erro ao buscar dados de {ticker}: {str(e)}")
            return None
    
    def carregar_dados_batch(self, tickers=None):
        """
        Carrega dados de múltiplos tickers em batch com barra de progresso.
        """
        if tickers is None:
            tickers = self.tickers_exemplo
        
        dados_lista = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, ticker in enumerate(tickers):
            status_text.text(f"Buscando dados de {ticker}... ({i+1}/{len(tickers)})")
            dados = self.buscar_dados_fundamentalistas(ticker)
            if dados:
                dados_lista.append(dados)
            progress_bar.progress((i + 1) / len(tickers))
        
        status_text.empty()
        return pd.DataFrame(dados_lista)
    
    def calcular_scores(self, df):
        """
        Calcula scores normalizados de valuation e qualidade, e score final.
        """
        if df.empty:
            return df
        
        # Normalização inversa para métricas onde menor é melhor
        df['pl_score'] = 1 / (df['pl'] + 1)   # evitar divisão por zero
        df['pvp_score'] = 1 / (df['pvp'] + 1)
        df['ev_ebitda_score'] = 1 / (df['ev_ebitda'] + 1)
        df['div_liq_score'] = 1 / (df['div_liq_ebitda'].abs() + 1)
        
        # Normalização direta para métricas onde maior é melhor
        df['dy_score'] = df['dy'] / 100 if 'dy' in df else 0
        df['roe_score'] = df['roe'] / 100
        df['margem_score'] = df['margem_ebit'] / 100
        df['cresc_score'] = df['crescimento_receita'] / 100 if 'crescimento_receita' in df else 0
        
        # Scores agregados (média simples das normalizadas)
        df['score_valuation'] = df[[
            'pl_score', 'pvp_score', 'ev_ebitda_score', 'dy_score'
        ]].mean(axis=1, skipna=True)
        
        df['score_qualidade'] = df[[
            'roe_score', 'margem_score', 'div_liq_score', 'cresc_score'
        ]].mean(axis=1, skipna=True)
        
        # Score final ponderado
        df['score_final'] = (
            df['score_valuation'] * self.pesos['valuation'] +
            df['score_qualidade'] * self.pesos['qualidade']
        )
        
        # Classificação qualitativa
        def classificar(score):
            if score >= 0.7: return "Excelente"
            elif score >= 0.5: return "Boa"
            elif score >= 0.3: return "Média"
            else: return "Baixa"
        
        df['classificacao'] = df['score_final'].apply(classificar)
        
        return df.sort_values('score_final', ascending=False)

def main():
    st.markdown('<h1 class="main-header">B3 Quant Analyzer</h1>', unsafe_allow_html=True)
    st.markdown("Análise quantitativa de ações da B3: valuation atrativo + qualidade fundamental")
    
    analyzer = B3QuantAnalyzer()
    
    # Barra lateral - Filtros
    with st.sidebar:
        st.header("Configurações da Análise")
        
        # Seleção de tickers (por enquanto, usa a lista fixa; pode expandir com upload)
        tickers_selecionados = st.multiselect(
            "Tickers para analisar",
            options=analyzer.tickers_exemplo,
            default=analyzer.tickers_exemplo[:10],
            help="Selecione as ações que deseja incluir na análise"
        )
        
        st.subheader("Filtros de Qualidade")
        min_roe = st.slider("ROE mínimo (%)", 0.0, 50.0, 10.0)
        max_div_ebitda = st.slider("Dívida Líquida/EBITDA máxima", 0.0, 5.0, 3.0)
        
        st.subheader("Filtros de Valuation")
        max_pl = st.slider("P/L máximo", 5.0, 50.0, 20.0)
        min_dy = st.slider("Dividend Yield mínimo (%)", 0.0, 10.0, 3.0)
        
        if st.button("Executar Análise", type="primary"):
            if not tickers_selecionados:
                st.error("Selecione pelo menos um ticker.")
                return
            
            with st.spinner("Carregando dados da B3..."):
                df_raw = analyzer.carregar_dados_batch(tickers_selecionados)
            
            if df_raw.empty:
                st.error("Nenhum dado válido foi obtido. Verifique conexão ou tickers.")
                return
            
            df = analyzer.calcular_scores(df_raw)
            
            # Aplicar filtros
            df_filtrado = df[
                (df['roe'] >= min_roe) &
                (df['div_liq_ebitda'] <= max_div_ebitda) &
                (df['pl'] <= max_pl) &
                (df['dy'] >= min_dy)
            ].copy()
            
            st.session_state['df_analise'] = df
            st.session_state['df_filtrado'] = df_filtrado
            st.success(f"Análise concluída! {len(df_filtrado)} ações atendem aos critérios.")
    
    # Conteúdo principal - Tabs
    if 'df_filtrado' in st.session_state and not st.session_state['df_filtrado'].empty:
        df_filtrado = st.session_state['df_filtrado']
        df_completo = st.session_state['df_analise']
        
        tab1, tab2, tab3, tab4 = st.tabs(["Dashboard", "Detalhes por Ação", "Dados Completos", "Metodologia"])
        
        with tab1:
            st.subheader("Resumo das Melhores Oportunidades")
            st.dataframe(
                df_filtrado[['ticker', 'nome', 'setor', 'preco', 'score_final', 'classificacao']]
                .head(10)
                .round(2)
            )
            
            # Gráfico de dispersão
            fig_scatter = px.scatter(
                df_filtrado,
                x='pl',
                y='roe',
                size='dy',
                color='score_final',
                hover_name='ticker',
                title="Valuation vs Qualidade (ROE)",
                labels={'pl': 'P/L', 'roe': 'ROE (%)', 'dy': 'DY (%)'}
            )
            st.plotly_chart(fig_scatter, use_container_width=True)
        
        with tab2:
            st.subheader("Análise Detalhada de Ação")
            ticker_selecionado = st.selectbox(
                "Selecione uma ação:",
                options=df_filtrado['ticker'].tolist()
            )
            
            if ticker_selecionado:
                row = df_filtrado[df_filtrado['ticker'] == ticker_selecionado].iloc[0]
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**Dados Fundamentais:**")
                    st.write(f"**Nome:** {row['nome']}")
                    st.write(f"**Setor:** {analyzer.setores_map.get(row['setor'], row['setor'])}")
                    st.write(f"**Preço Atual:** R$ {row['preco']:.2f}")
                    st.write(f"**Score Final:** {row['score_final']:.2f} ({row['classificacao']})")
                    
                    st.write("**Valuation:**")
                    st.write(f"- P/L: {row['pl']:.1f}")
                    st.write(f"- P/VP: {row['pvp']:.2f}")
                    st.write(f"- DY: {row['dy']:.1f}%")
                    
                    st.write("**Qualidade:**")
                    st.write(f"- ROE: {row['roe']:.1f}%")
                    st.write(f"- Margem EBIT: {row['margem_ebit']:.1f}%")
                    st.write(f"- Dív/EBITDA: {row['div_liq_ebitda']:.1f}")
                
                with col2:
                    # Gráfico radar simples
                    categorias = ['P/L (inv)', 'P/VP (inv)', 'DY', 'ROE', 'Margem EBIT', 'Dív/EBITDA (inv)']
                    valores = [
                        1 / (row['pl'] + 1) if not np.isnan(row['pl']) else 0,
                        1 / (row['pvp'] + 1) if not np.isnan(row['pvp']) else 0,
                        row['dy'] / 10 if not np.isnan(row['dy']) else 0,
                        row['roe'] / 50 if not np.isnan(row['roe']) else 0,
                        row['margem_ebit'] / 50 if not np.isnan(row['margem_ebit']) else 0,
                        1 / (row['div_liq_ebitda'] + 1) if not np.isnan(row['div_liq_ebitda']) else 0
                    ]
                    
                    fig_radar = go.Figure(data=go.Scatterpolar(
                        r=valores + [valores[0]],
                        theta=categorias + [categorias[0]],
                        fill='toself'
                    ))
                    fig_radar.update_layout(
                        polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
                        showlegend=False,
                        title="Radar de Métricas Normalizadas"
                    )
                    st.plotly_chart(fig_radar, use_container_width=True)
        
        with tab3:
            st.subheader("Dataset Completo")
            mostrar_todos = st.checkbox("Mostrar todos os dados (sem filtros)", value=False)
            df_exibir = df_completo if mostrar_todos else df_filtrado
            
            colunas_padrao = ['ticker', 'nome', 'setor', 'preco', 'pl', 'pvp', 'roe', 'dy', 'score_final', 'classificacao']
            colunas_selecionadas = st.multiselect(
                "Colunas para exibir:",
                options=df_exibir.columns.tolist(),
                default=[c for c in colunas_padrao if c in df_exibir.columns]
            )
            
            if colunas_selecionadas:
                st.dataframe(df_exibir[colunas_selecionadas].round(2))
                
                csv = df_exibir[colunas_selecionadas].to_csv(index=False).encode('utf-8')
                st.download_button(
                    "Baixar CSV",
                    csv,
                    f"b3_quant_{datetime.now().strftime('%Y%m%d')}.csv",
                    "text/csv"
                )
        
        with tab4:
            st.subheader("Metodologia de Análise")
            st.markdown("""
            ### Pilares da Análise
            
            **1. Valuation Atrativo (50%)**  
            - P/L baixo  
            - P/VP descontado  
            - EV/EBITDA atrativo  
            - Dividend Yield elevado  
            
            **2. Qualidade Fundamental (50%)**  
            - ROE elevado  
            - Margens operacionais saudáveis  
            - Alavancagem controlada (Dívida Líquida/EBITDA)  
            - Crescimento de receita positivo  
            
            **Classificação Final**  
            - Excelente: score ≥ 0.7  
            - Boa: 0.5 ≤ score < 0.7  
            - Média: 0.3 ≤ score < 0.5  
            - Baixa: score < 0.3  
            
            **Aviso**  
            Dados obtidos via yfinance (Yahoo Finance). Podem apresentar defasagem ou inconsistências.  
            Não constitui recomendação de investimento. Complemente com análise qualitativa.
            """)
    
    else:
        # Tela inicial
        st.info("""
        ### Bem-vindo ao B3 Quant Analyzer
        
        Configure os filtros na barra lateral esquerda e clique em "Executar Análise" para iniciar.
        
        A ferramenta identifica ações com:
        - Valuation atrativo (P/L, P/VP, DY)
        - Qualidade fundamental sólida (ROE, margens, baixa dívida)
        """)

if __name__ == "__main__":
    main()
