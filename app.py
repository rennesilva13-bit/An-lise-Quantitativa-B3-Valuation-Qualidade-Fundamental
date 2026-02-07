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
from datetime import datetime, timedelta
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
        # Mapeamento de setores B3
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
        
        # Tickers de exemplo da B3 (substituir por lista completa)
        self.tickers_exemplo = {
            'ITUB4.SA': 'FINL',
            'BBDC4.SA': 'FINL', 
            'SANB11.SA': 'FINL',
            'TAEE11.SA': 'UTILS',
            'SBSP3.SA': 'UTILS',
            'MGLU3.SA': 'CONS_DUR',
            'LREN3.SA': 'CONS_DUR',
            'VIVT3.SA': 'COMM',
            'PETR4.SA': 'ENER',
            'VALE3.SA': 'MATR',
            'CSNA3.SA': 'MATR',
            'GOLL4.SA': 'INDS',
            'EMBR3.SA': 'INDS',
            'RADL3.SA': 'CONS_STAP',
            'JBSS3.SA': 'CONS_STAP',
            'HAPV3.SA': 'SAUDE',
            'QUAL3.SA': 'CONS_STAP'
        }
        
        # Parâmetros de scoring
        self.pesos = {
            'valuation': 0.5,
            'qualidade': 0.5
        }
        
    def buscar_dados_fundamentalistas(self, ticker):
        """
        Busca dados fundamentalistas usando yfinance.
        Retorna dicionário com métricas principais.
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
                dy = dy * 100  # Converter para %
            
            # Métricas de Qualidade
            roe = info.get('returnOnEquity', np.nan)
            if not np.isnan(roe):
                roe = roe * 100  # Converter para %
            
            margem_ebit = info.get('ebitdaMargins', np.nan)
            if not np.isnan(margem_ebit):
                margem_ebit = margem_ebit * 100
            
            div_liq_ebitda = info.get('debtToEbitda', np.nan)
            
            # Dados de preço
            preco_atual = info.get('currentPrice', np.nan)
            preco_52w_high = info.get('fiftyTwoWeekHigh', np.nan)
            preco_52w_low = info.get('fiftyTwoWeekLow', np.nan)
            
            # Crescimento (usando receita)
            receita_crescimento = info.get('revenueGrowth', np.nan)
            if not np.isnan(receita_crescimento):
                receita_crescimento = receita_crescimento * 100
            
            return {
                'ticker': ticker.replace('.SA', ''),
                'nome': info.get('longName', ticker),
                'setor': self.tickers_exemplo.get(ticker, 'OUTROS'),
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
            st.warning(f"Erro ao buscar dados de {ticker}: {e}")
            return None
    
    def carregar_dados_batch(self, tickers=None):
        """
        Carrega dados de múltiplos tickers em batch.
        """
        if tickers is None:
            tickers = list(self.tickers_exemplo.keys())
        
        dados_lista = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, ticker in enumerate(tickers):
            status_text.text(f"Buscando dados de {ticker}... ({i+1}/{len(tickers)})")
            dados = self.buscar_dados_fundamentalistas(ticker)
            if dados:
                dados_lista.append(dados)
            progress_bar.progress((i + 1) / len(tickers))
        
        progress_bar.empty()
        status_text.empty()
        
        if dados_lista:
            df = pd.DataFrame(dados_lista)
            return df
        else:
            return pd.DataFrame()
    
    def calcular_scores(self, df):
        """
        Calcula scores de valuation e qualidade fundamental.
        """
        df = df.copy()
        
        # Normalizar métricas (min-max scaling)
        def normalize(series, ascending=True):
            min_val = series.min()
            max_val = series.max()
            if max_val == min_val:
                return pd.Series([0.5] * len(series), index=series.index)
            normalized = (series - min_val) / (max_val - min_val)
            return normalized if ascending else 1 - normalized
        
        # Score Valuation (quanto menor, melhor)
        df['score_pl'] = normalize(df['pl'], ascending=True)
        df['score_pvp'] = normalize(df['pvp'], ascending=True)
        df['score_ev_ebitda'] = normalize(df['ev_ebitda'], ascending=True)
        df['score_dy'] = normalize(df['dy'], ascending=False)  # DY: quanto maior, melhor
        
        df['score_valuation'] = (
            df['score_pl'].fillna(0) * 0.3 +
            df['score_pvp'].fillna(0) * 0.3 +
            df['score_ev_ebitda'].fillna(0) * 0.2 +
            df['score_dy'].fillna(0) * 0.2
        )
        
        # Score Qualidade (quanto maior, melhor)
        df['score_roe'] = normalize(df['roe'], ascending=False)
        df['score_margem'] = normalize(df['margem_ebit'], ascending=False)
        df['score_divida'] = normalize(df['div_liq_ebitda'], ascending=True)  # Dívida: quanto menor, melhor
        df['score_crescimento'] = normalize(df['crescimento_receita'], ascending=False)
        
        df['score_qualidade'] = (
            df['score_roe'].fillna(0) * 0.35 +
            df['score_margem'].fillna(0) * 0.25 +
            df['score_divida'].fillna(0) * 0.2 +
            df['score_crescimento'].fillna(0) * 0.2
        )
        
        # Score Final
        df['score_final'] = (
            df['score_valuation'] * self.pesos['valuation'] +
            df['score_qualidade'] * self.pesos['qualidade']
        )
        
        # Classificação
        df['classificacao'] = pd.cut(
            df['score_final'],
            bins=[0, 0.3, 0.5, 0.7, 1.0],
            labels=['Baixa', 'Média', 'Boa', 'Excelente'],
            include_lowest=True
        )
        
        return df
    
    def aplicar_filtros(self, df, filtros):
        """
        Aplica filtros ao DataFrame conforme parâmetros do usuário.
        """
        df_filtrado = df.copy()
        
        # Filtro por setor
        if filtros.get('setores'):
            df_filtrado = df_filtrado[df_filtrado['setor'].isin(filtros['setores'])]
        
        # Filtro por score mínimo
        if filtros.get('score_min'):
            df_filtrado = df_filtrado[df_filtrado['score_final'] >= filtros['score_min']]
        
        # Filtros de valuation
        if filtros.get('pl_max'):
            df_filtrado = df_filtrado[df_filtrado['pl'] <= filtros['pl_max']]
        if filtros.get('pvp_max'):
            df_filtrado = df_filtrado[df_filtrado['pvp'] <= filtros['pvp_max']]
        if filtros.get('dy_min'):
            df_filtrado = df_filtrado[df_filtrado['dy'] >= filtros['dy_min']]
        
        # Filtros de qualidade
        if filtros.get('roe_min'):
            df_filtrado = df_filtrado[df_filtrado['roe'] >= filtros['roe_min']]
        if filtros.get('div_liq_max'):
            df_filtrado = df_filtrado[df_filtrado['div_liq_ebitda'] <= filtros['div_liq_max']]
        
        return df_filtrado


class Visualizador:
    """
    Classe para criação de visualizações e gráficos.
    """
    
    @staticmethod
    def criar_scatter_valuation_qualidade(df):
        """
        Cria scatter plot: Valuation vs Qualidade.
        """
        fig = px.scatter(
            df,
            x='score_valuation',
            y='score_qualidade',
            size='preco',
            color='setor',
            hover_name='ticker',
            hover_data=['nome', 'pl', 'roe', 'dy', 'score_final'],
            title='Matriz: Valuation vs Qualidade Fundamental',
            labels={
                'score_valuation': 'Score Valuation (0-1)',
                'score_qualidade': 'Score Qualidade (0-1)'
            },
            height=600
        )
        
        # Linhas de referência
        fig.add_hline(y=0.5, line_dash="dash", line_color="gray")
        fig.add_vline(x=0.5, line_dash="dash", line_color="gray")
        
        fig.update_layout(
            xaxis_title="Score Valuation (quanto menor o P/L, P/VP, melhor)",
            yaxis_title="Score Qualidade (quanto maior ROE, margem, melhor)",
            showlegend=True
        )
        
        return fig
    
    @staticmethod
    def criar_ranking_top10(df):
        """
        Cria tabela com top 10 ações por score final.
        """
        top10 = df.nlargest(10, 'score_final')[[
            'ticker', 'nome', 'setor', 'score_final', 'classificacao',
            'pl', 'pvp', 'roe', 'dy'
        ]].round(2)
        
        return top10
    
    @staticmethod
    def criar_distribuicao_setores(df):
        """
        Cria gráfico de distribuição por setor.
        """
        distribuicao = df['setor'].value_counts().reset_index()
        distribuicao.columns = ['Setor', 'Quantidade']
        
        fig = px.pie(
            distribuicao,
            values='Quantidade',
            names='Setor',
            title='Distribuição de Oportunidades por Setor',
            height=400
        )
        
        return fig
    
    @staticmethod
    def criar_radar_score(ticker_data):
        """
        Cria gráfico radar para análise detalhada de uma ação.
        """
        if ticker_data.empty:
            return None
        
        row = ticker_data.iloc[0]
        
        categorias = ['P/L', 'P/VP', 'ROE', 'DY', 'Dív/EBITDA']
        valores = [
            1 - (row['score_pl'] if not pd.isna(row['score_pl']) else 0),
            1 - (row['score_pvp'] if not pd.isna(row['score_pvp']) else 0),
            row['score_roe'] if not pd.isna(row['score_roe']) else 0,
            row['score_dy'] if not pd.isna(row['score_dy']) else 0,
            1 - (row['score_divida'] if not pd.isna(row['score_divida']) else 0)
        ]
        
        fig = go.Figure(data=go.Scatterpolar(
            r=valores,
            theta=categorias,
            fill='toself',
            name=row['ticker']
        ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 1]
                )
            ),
            showlegend=False,
            title=f"Perfil de Score: {row['ticker']} - {row['nome']}"
        )
        
        return fig
    
    @staticmethod
    def criar_histograma_scores(df):
        """
        Cria histograma da distribuição dos scores finais.
        """
        fig = px.histogram(
            df,
            x='score_final',
            nbins=20,
            title='Distribuição dos Scores Finais',
            labels={'score_final': 'Score Final'},
            height=400
        )
        
        fig.add_vline(
            x=df['score_final'].median(),
            line_dash="dash",
            line_color="red",
            annotation_text=f"Mediana: {df['score_final'].median():.2f}"
        )
        
        return fig


def main():
    """
    Função principal da aplicação Streamlit.
    """
    
    # Cabeçalho
    st.markdown('<div class="main-header">📈 B3 Quant Analyzer</div>', unsafe_allow_html=True)
    st.markdown("""
    *Plataforma de análise quantitativa para identificação de oportunidades na B3 com base em valuation atrativo e qualidade fundamental.*
    """)
    
    # Inicializar analisador
    analyzer = B3QuantAnalyzer()
    visualizador = Visualizador()
    
    # Sidebar - Configurações
    st.sidebar.header("⚙️ Configurações")
    
    # Opção de carregar dados
    st.sidebar.subheader("Fonte de Dados")
    opcao_dados = st.sidebar.radio(
        "Selecione:",
        ["Carregar Dados Reais (yfinance)", "Usar Dados de Exemplo"],
        index=1
    )
    
    # Filtros
    st.sidebar.subheader("Filtros de Seleção")
    
    # Filtro por setor
    setores_disponiveis = list(analyzer.setores_map.keys())
    setores_selecionados = st.sidebar.multiselect(
        "Setores:",
        options=setores_disponiveis,
        default=[],
        format_func=lambda x: analyzer.setores_map[x]
    )
    
    # Filtros de Valuation
    st.sidebar.subheader("Filtros de Valuation")
    pl_max = st.sidebar.slider("P/L Máximo:", 0, 50, 25)
    pvp_max = st.sidebar.slider("P/VP Máximo:", 0.0, 5.0, 2.0, 0.1)
    dy_min = st.sidebar.slider("DY Mínimo (%):", 0.0, 15.0, 0.0, 0.5)
    
    # Filtros de Qualidade
    st.sidebar.subheader("Filtros de Qualidade")
    roe_min = st.sidebar.slider("ROE Mínimo (%):", 0.0, 30.0, 0.0, 1.0)
    div_liq_max = st.sidebar.slider("Dív/EBITDA Máximo:", 0.0, 10.0, 5.0, 0.5)
    
    # Score mínimo
    score_min = st.sidebar.slider("Score Final Mínimo:", 0.0, 1.0, 0.5, 0.05)
    
    # Botão para executar análise
    if st.sidebar.button("🚀 Executar Análise"):
        with st.spinner("Processando análise..."):
            
            # Carregar dados
            if opcao_dados == "Carregar Dados Reais (yfinance)":
                df_raw = analyzer.carregar_dados_batch()
            else:
                # Dados de exemplo para demonstração
                df_raw = pd.DataFrame({
                    'ticker': ['ITUB4', 'BBDC4', 'TAEE11', 'MGLU3', 'PETR4', 'VALE3', 'VIVT3', 'RADL3'],
                    'nome': ['Itaú Unibanco', 'Banco Bradesco', 'Taesa', 'Magazine Luiza', 
                            'Petrobras', 'Vale', 'Telefônica Vivo', 'Raia Drogasil'],
                    'setor': ['FINL', 'FINL', 'UTILS', 'CONS_DUR', 'ENER', 'MATR', 'COMM', 'SAUDE'],
                    'preco': [35.5, 18.2, 42.1, 2.8, 38.9, 72.3, 15.6, 28.4],
                    'pl': [9.2, 10.1, 18.3, 12.5, 6.8, 8.5, 15.2, 22.1],
                    'pvp': [1.1, 0.9, 2.1, 1.8, 1.3, 1.6, 2.5, 3.2],
                    'ev_ebitda': [7.5, 8.2, 12.1, 9.8, 5.2, 6.1, 11.3, 14.5],
                    'dy': [6.8, 7.2, 4.1, 0.5, 8.5, 5.8, 3.2, 1.8],
                    'roe': [16.5, 14.8, 12.1, 9.5, 18.2, 15.6, 8.9, 11.3],
                    'margem_ebit': [35.2, 32.1, 45.6, 8.2, 28.5, 32.8, 25.1, 6.8],
                    'div_liq_ebitda': [1.2, 0.9, 2.8, 1.5, 0.8, 1.1, 2.2, 0.6],
                    'crescimento_receita': [8.5, 6.2, 12.3, 15.8, 10.2, 9.5, 5.1, 18.2],
                    'preco_52w_high': [42.5, 22.1, 48.2, 8.5, 45.2, 85.1, 18.9, 35.6],
                    'preco_52w_low': [28.3, 14.5, 32.1, 2.1, 28.5, 58.2, 12.3, 22.1],
                    'volume_medio': [25000000, 18000000, 3500000, 45000000, 32000000, 28000000, 8000000, 5000000]
                })
            
            if df_raw.empty:
                st.error("❌ Nenhum dado foi carregado. Verifique sua conexão com a internet.")
                return
            
            # Calcular scores
            df_com_scores = analyzer.calcular_scores(df_raw)
            
            # Aplicar filtros
            filtros = {
                'setores': setores_selecionados,
                'score_min': score_min,
                'pl_max': pl_max,
                'pvp_max': pvp_max,
                'dy_min': dy_min,
                'roe_min': roe_min,
                'div_liq_max': div_liq_max
            }
            
            df_filtrado = analyzer.aplicar_filtros(df_com_scores, filtros)
            
            # Armazenar no session_state
            st.session_state['df_completo'] = df_com_scores
            st.session_state['df_filtrado'] = df_filtrado
            st.session_state['ultima_atualizacao'] = datetime.now()
            
            st.success(f"✅ Análise concluída! {len(df_filtrado)} oportunidades identificadas.")
    
    # Exibir resultados se existirem
    if 'df_filtrado' in st.session_state:
        df_completo = st.session_state['df_completo']
        df_filtrado = st.session_state['df_filtrado']
        
        # Tabs para organização
        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 Dashboard", 
            "📈 Visualizações", 
            "📋 Dados Completos", 
            "ℹ️ Metodologia"
        ])
        
        # Tab 1: Dashboard
        with tab1:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    label="Total de Ações Analisadas",
                    value=len(df_completo)
                )
            with col2:
                st.metric(
                    label="Oportunidades Identificadas",
                    value=len(df_filtrado)
                )
            with col3:
                st.metric(
                    label="Score Médio",
                    value=f"{df_filtrado['score_final'].mean():.2f}"
                )
            with col4:
                st.metric(
                    label="Melhor Score",
                    value=f"{df_filtrado['score_final'].max():.2f}"
                )
            
            st.markdown("---")
            
            # Top 10 ranking
            st.subheader("🏆 Top 10 Oportunidades")
            top10 = visualizador.criar_ranking_top10(df_filtrado)
            st.dataframe(
                top10.style.background_gradient(cmap='YlOrRd', subset=['score_final']),
                use_container_width=True
            )
            
            # Distribuição por classificação
            col1, col2 = st.columns(2)
            with col1:
                classificacao_counts = df_filtrado['classificacao'].value_counts()
                st.bar_chart(classificacao_counts)
            
            with col2:
                st.write("**Legenda de Classificação:**")
                st.write("- 🟢 **Excelente**: Score ≥ 0.7")
                st.write("- 🔵 **Boa**: 0.5 ≤ Score < 0.7")
                st.write("- 🟡 **Média**: 0.3 ≤ Score < 0.5")
                st.write("- 🔴 **Baixa**: Score < 0.3")
        
        # Tab 2: Visualizações
        with tab2:
            col1, col2 = st.columns(2)
            
            with col1:
                # Scatter Valuation vs Qualidade
                fig_scatter = visualizador.criar_scatter_valuation_qualidade(df_filtrado)
                st.plotly_chart(fig_scatter, use_container_width=True)
            
            with col2:
                # Distribuição por setor
                fig_pie = visualizador.criar_distribuicao_setores(df_filtrado)
                st.plotly_chart(fig_pie, use_container_width=True)
            
            # Histograma de scores
            fig_hist = visualizador.criar_histograma_scores(df_filtrado)
            st.plotly_chart(fig_hist, use_container_width=True)
            
            # Análise detalhada de uma ação
            st.subheader("🔍 Análise Detalhada de Ação")
            ticker_selecionado = st.selectbox(
                "Selecione uma ação:",
                options=df_filtrado['ticker'].tolist()
            )
            
            if ticker_selecionado:
                dados_ticker = df_filtrado[df_filtrado['ticker'] == ticker_selecionado]
                col1, col2 = st.columns(2)
                
                with col1:
                    # Dados fundamentais
                    st.write("**Dados Fundamentais:**")
                    st.write(f"**Nome:** {dados_ticker['nome'].values[0]}")
                    st.write(f"**Setor:** {analyzer.setores_map.get(dados_ticker['setor'].values[0], dados_ticker['setor'].values[0])}")
                    st.write(f"**Preço Atual:** R$ {dados_ticker['preco'].values[0]:.2f}")
                    st.write(f"**Score Final:** {dados_ticker['score_final'].values[0]:.2f} ({dados_ticker['classificacao'].values[0]})")
                    
                    st.write("**Valuation:**")
                    st.write(f"- P/L: {dados_ticker['pl'].values[0]:.1f}")
                    st.write(f"- P/VP: {dados_ticker['pvp'].values[0]:.2f}")
                    st.write(f"- DY: {dados_ticker['dy'].values[0]:.1f}%")
                    
                    st.write("**Qualidade:**")
                    st.write(f"- ROE: {dados_ticker['roe'].values[0]:.1f}%")
                    st.write(f"- Margem EBIT: {dados_ticker['margem_ebit'].values[0]:.1f}%")
                    st.write(f"- Dív/EBITDA: {dados_ticker['div_liq_ebitda'].values[0]:.1f}")
                
                with col2:
                    # Gráfico radar
                    fig_radar = visualizador.criar_radar_score(dados_ticker)
                    if fig_radar:
                        st.plotly_chart(fig_radar, use_container_width=True)
        
        # Tab 3: Dados Completos
        with tab3:
            st.subheader("📋 Dataset Completo")
            
            # Opções de visualização
            col1, col2 = st.columns(2)
            with col1:
                mostrar_todos = st.checkbox("Mostrar todos os dados (sem filtros)", value=False)
            
            df_exibir = df_completo if mostrar_todos else df_filtrado
            
            # Seleção de colunas
            colunas_disponiveis = df_exibir.columns.tolist()
            colunas_padrao = ['ticker', 'nome', 'setor', 'preco', 'pl', 'pvp', 'roe', 'dy', 'score_final', 'classificacao']
            colunas_selecionadas = st.multiselect(
                "Selecione colunas para exibir:",
                options=colunas_disponiveis,
                default=[c for c in colunas_padrao if c in colunas_disponiveis]
            )
            
            if colunas_selecionadas:
                df_visualizacao = df_exibir[colunas_selecionadas].round(2)
                st.dataframe(df_visualizacao, use_container_width=True)
                
                # Botão de download
                csv = df_visualizacao.to_csv(index=False)
                st.download_button(
                    label="📥 Download CSV",
                    data=csv,
                    file_name=f"b3_quant_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
        
        # Tab 4: Metodologia
        with tab4:
            st.subheader("📖 Metodologia de Análise")
            
            st.markdown("""
            ### Dois Pilares Fundamentais
            
            #### 1. Valuation Atrativo (50% do score)
            - **P/L (Preço/Lucro)**: Empresas com P/L abaixo da média do mercado
            - **P/VP (Preço/Valor Patrimonial)**: Busca por desconto em relação ao valor contábil
            - **EV/EBITDA**: Avaliação da empresa como um todo
            - **DY (Dividend Yield)**: Retorno por dividendos atrativo
            
            #### 2. Qualidade Fundamental (50% do score)
            - **ROE (Return on Equity)**: Eficiência na geração de lucro sobre patrimônio
            - **Margem EBIT**: Capacidade de geração de caixa operacional
            - **Dívida Líquida/EBITDA**: Alavancagem financeira controlada
            - **Crescimento de Receita**: Trajetória de crescimento sustentável
            
            ### Classificação Final
            - **Excelente**: Score ≥ 0.7
            - **Boa**: 0.5 ≤ Score < 0.7
            - **Média**: 0.3 ≤ Score < 0.5
            - **Baixa**: Score < 0.3
            
            ### Limitações
            - Dados dependentes da API yfinance (pode ter defasagem)
            - Métricas baseadas em dados históricos (não garantem desempenho futuro)
            - Recomenda-se complementar com análise qualitativa
            """)
    
    else:
        # Mensagem inicial
        st.info("""
        ### 📌 Instruções de Uso
        
        1. **Configure os filtros** na barra lateral à esquerda
        2. **Selecione os setores** de interesse
        3. **Ajuste os parâmetros** de valuation e qualidade
        4. **Clique em "Executar Análise"** para iniciar o processamento
        
        A análise irá identificar oportunidades com base em:
        - ✅ **Valuation atrativo** (P/L, P/VP, DY baixos)
        - ✅ **Qualidade fundamental** (ROE, margens, baixa dívida)
        """)
        
        # Exemplo de visualização inicial
        st.subheader("🎯 Exemplo de Análise")
        st.markdown("""
        *Após executar a análise, você terá acesso a:*
        
        - **Dashboard** com métricas resumidas e top 10 oportunidades
        - **Visualizações interativas** (scatter, gráficos de distribuição)
        - **Análise detalhada** por ação com gráfico radar
        - **Download dos dados** em formato CSV
        """)


if __name__ == "__main__":
    main()