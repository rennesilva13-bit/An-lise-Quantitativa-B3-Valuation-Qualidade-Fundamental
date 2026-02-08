"""
B3 Quant Analyzer - Value Investing & Valuation
===============================================
Aplicação Streamlit para análise fundamentalista e cálculo de valor intrínseco.
Foco: Longo prazo, Dividendos e Segurança (Graham & Bazin).
Correção: Inclui CSS para visibilidade em Dark Mode e Matplotlib para tabelas.

Autor: Analista Quantitativo
Data: 2026
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
import warnings

# Ignorar avisos de versões futuras
warnings.filterwarnings('ignore')

# --- Configuração da Página ---
st.set_page_config(
    page_title="B3 Value Investing",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS Customizado (Correção de Visibilidade) ---
# Este bloco força a cor do texto para preto dentro dos cards,
# garantindo leitura mesmo no Modo Escuro.
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
    
    /* Estilo para os cartões de métrica (stMetric) */
    div[data-testid="stMetric"] {
        background-color: #f0f2f6 !important; /* Fundo cinza claro */
        border-radius: 10px;
        padding: 15px;
        border-left: 5px solid #0066cc;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    
    /* Forçar Labels (Títulos) para cinza escuro */
    div[data-testid="stMetric"] label {
        color: #444 !important;
        font-weight: 600 !important;
    }
    
    /* Forçar Valores (Números grandes) para preto */
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #000 !important;
        font-weight: bold !important;
    }
    
    /* Forçar Delta (Variação pequena) para cor escura */
    div[data-testid="stMetricDelta"] {
        color: #333 !important;
    }
    
    /* Ajustes gerais */
    .stDataFrame { border-radius: 10px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

class B3Fundamentalist:
    """
    Motor de análise focado em Valuation e Segurança.
    """
    
    def __init__(self):
        # Tickers padrão para facilitar o uso
        self.tickers_padrao = [
            'BBAS3', 'ITUB4', 'BBDC4', 'SANB11', # Bancos
            'TAEE11', 'TRPL4', 'CPLE6', 'EGIE3', # Elétricas
            'VALE3', 'CSNA3', 'GGBR4',           # Commodities
            'WEGE3', 'PSSA3', 'BBSE3', 'CXSE3',  # Seguros/Indústria
            'SAPR11', 'CSMG3', 'CMIG4', 'KLBN11' # Saneamento/Papel
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

    @st.cache_data(ttl=3600) # Cache de 1 hora
    def buscar_dados(_self, tickers):
        """
        Busca dados fundamentalistas e calcula indicadores.
        """
        dados_lista = []
        
        # Barra de progresso visual
        progress_bar = st.progress(0)
        status_text = st.empty()
        total = len(tickers)
        
        for i, ticker_raw in enumerate(tickers):
            ticker = _self._tratar_ticker(ticker_raw)
            status_text.text(f"Analisando: {ticker} ({i+1}/{total})")
            
            try:
                stock = yf.Ticker(ticker)
                
                # Preço Atual (Fast Info é mais rápido)
                try:
                    price = stock.fast_info.last_price
                except:
                    # Fallback se fast_info falhar
                    hist = stock.history(period="1d")
                    if not hist.empty:
                        price = hist['Close'].iloc[-1]
                    else:
                        continue # Pula se não tiver preço

                # Dados Fundamentais (Info)
                info = stock.info
                
                # Extração Segura de Dados (Evita erros com None/Zeros)
                lpa = info.get('trailingEps', 0) or 0
                vpa = info.get('bookValue', 0) or 0
                roe = info.get('returnOnEquity', 0) or 0
                divida_ebitda = info.get('debtToEbitda', 0) or 0
                margem_liq = info.get('profitMargins', 0) or 0
                dy_rate = info.get('dividendRate', 0) or 0  # Em R$
                dy_percent = info.get('dividendYield', 0) or 0 # Em %
                volume = info.get('averageVolume', 0) or 0
                pl = info.get('trailingPE', 0) or 0
                pvp = info.get('priceToBook', 0) or 0
                
                # Cálculos de Valuation
                valor_graham = _self.calcular_valor_graham(lpa, vpa)
                valor_bazin = _self.calcular_valor_bazin(dy_rate)
                
                # Margem de Segurança (Graham)
                if valor_graham > 0:
                    ms_graham = ((valor_graham - price) / price) * 100
                else:
                    ms_graham = -100 # Sem valor intrínseco calculado
                
                # --- Lógica de "Armadilha" (Trap) ---
                is_trap = False
                motivo_trap = []
                
                if roe < 0.05: # ROE menor que 5%
                    is_trap = True
                    motivo_trap.append("Rentabilidade Baixa")
                if divida_ebitda > 4: # Dívida alta
                    is_trap = True
                    motivo_trap.append("Dívida Alta")
                if margem_liq < 0.03: # Margem muito apertada
                    is_trap = True
                    motivo_trap.append("Margem Perigosa")
                if volume < 500000: # Liquidez baixa (< 500k/dia)
                    is_trap = True
                    motivo_trap.append("Liquidez Baixa")

                dados_lista.append({
                    'Ticker': ticker.replace('.SA', ''),
                    'Preço Atual': price,
                    'Valor Graham': valor_graham,
                    'Valor Bazin': valor_bazin,
                    'MS Graham (%)': ms_graham,
                    'DY (%)': dy_percent * 100,
                    'P/L': pl,
                    'P/VP': pvp,
                    'ROE (%)': roe * 100,
                    'Margem Liq. (%)': margem_liq * 100,
                    'Dívida/EBITDA': divida_ebitda,
                    'Armadilha': "⚠️ SIM" if is_trap else "🛡️ NÃO",
                    'Alertas': ", ".join(motivo_trap) if motivo_trap else "OK",
                    'Score Magic': 0 # Placeholder
                })
                
            except Exception as e:
                # print(f"Erro ao processar {ticker}: {e}") # Debug apenas no terminal
                pass
                
            progress_bar.progress((i + 1) / total)
            
        progress_bar.empty()
        status_text.empty()
        
        return pd.DataFrame(dados_lista)

    def calcular_magic_score(self, df):
        """
        Ranking Combinado: Qualidade (ROE) + Preço (P/L).
        Empresas Boas e Baratas.
        """
        if df.empty: return df
        
        df = df.copy()
        
        # Filtra apenas empresas com lucro positivo para o ranking
        # (Empresas com prejuízo distorcem o ranking)
        mask_validos = df['P/L'] > 0
        
        # Se não houver empresas válidas, retorna original
        if not mask_validos.any():
            return df

        # Ranking de Preço: Menor P/L é melhor (Ascending=True)
        df.loc[mask_validos, 'Rank_PL'] = df.loc[mask_validos, 'P/L'].rank(ascending=True)
        
        # Ranking de Qualidade: Maior ROE é melhor (Ascending=False)
        df.loc[mask_validos, 'Rank_ROE'] = df.loc[mask_validos, 'ROE (%)'].rank(ascending=False)
        
        # Soma dos Ranks (Menor soma = Melhor colocação geral)
        df['Magic_Points'] = df['Rank_PL'] + df['Rank_ROE']
        
        # Normalização para Score 0 a 100 (para visualização fácil)
        # Onde 100 é a melhor empresa (menor pontuação de rank)
        min_pts = df['Magic_Points'].min()
        max_pts = df['Magic_Points'].max()
        
        if max_pts != min_pts:
            # Inverte a lógica: menos pontos = mais score
            df['Score Magic'] = 100 * (1 - (df['Magic_Points'] - min_pts) / (max_pts - min_pts))
        else:
            df['Score Magic'] = 50 # Caso base
            
        # Preencher NaNs (empresas com prejuízo) com 0
        df['Score Magic'] = df['Score Magic'].fillna(0)
            
        return df.sort_values('Score Magic', ascending=False)

def main():
    # Cabeçalho
    st.markdown('<div class="main-header">💎 B3 Quant Analyzer: Value Investing</div>', unsafe_allow_html=True)
    
    analyzer = B3Fundamentalist()
    
    # --- Sidebar (Lateral) ---
    st.sidebar.header("🔍 Configuração")
    
    # Seleção de Ativos
    modo_input = st.sidebar.radio(
        "Seleção de Ativos:", 
        ["Lista Padrão (Sugestão)", "Minha Carteira / Lista Personalizada"]
    )
    
    if modo_input == "Lista Padrão (Sugestão)":
        tickers_selecionados = analyzer.tickers_padrao
        st.sidebar.info(f"Analisando {len(tickers_selecionados)} ativos principais da bolsa.")
    else:
        lista_texto = st.sidebar.text_area(
            "Cole os tickers (separados por vírgula ou espaço):", 
            "WEGE3, ITSA4, FLRY3, LEVE3, OIBR3"
        )
        if lista_texto:
            import re
            # Divide por vírgula, espaço ou ponto e vírgula
            tickers_selecionados = re.split(r'[,\s;]+', lista_texto)
            tickers_selecionados = [t for t in tickers_selecionados if t] # Remove vazios
        else:
            tickers_selecionados = []

    # Filtros
    st.sidebar.markdown("---")
    st.sidebar.subheader("🛡️ Filtros de Segurança")
    
    filtrar_armadilhas = st.sidebar.checkbox(
        "Esconder 'Armadilhas'", 
        value=True,
        help="Remove empresas com prejuízo, dívida alta (>4x) ou baixa liquidez."
    )
    
    ms_minima = st.sidebar.slider(
        "Margem de Segurança Mínima (Graham) %", 
        -50, 100, 0,
        help="Quanto de desconto você quer em relação ao preço justo de Graham?"
    )
    
    # --- Botão de Ação ---
    if st.sidebar.button("🚀 Processar Valuation"):
        
        if not tickers_selecionados:
            st.warning("⚠️ Por favor, insira pelo menos um ticker.")
            return

        # 1. Buscar Dados
        df = analyzer.buscar_dados(tickers_selecionados)
        
        if df.empty:
            st.error("❌ Não foi possível coletar dados. Verifique sua conexão ou os tickers digitados.")
            return

        # 2. Calcular Magic Score
        df = analyzer.calcular_magic_score(df)
        
        # 3. Aplicar Filtros Visuais
        df_display = df.copy()
        
        if filtrar_armadilhas:
            df_display = df_display[df_display['Armadilha'].str.contains("NÃO")]
            
        df_display = df_display[df_display['MS Graham (%)'] >= ms_minima]

        if df_display.empty:
            st.warning("Nenhuma ação passou nos seus filtros rígidos. Tente diminuir a Margem de Segurança.")
            return

        # --- Dashboard ---
        
        # Tabela Principal
        st.subheader("🏆 Top Oportunidades (Ranking Magic Score)")
        
        # Colunas para exibir na tabela
        cols_view = [
            'Ticker', 'Preço Atual', 'Valor Graham', 'Valor Bazin', 
            'MS Graham (%)', 'DY (%)', 'ROE (%)', 'P/L', 
            'Score Magic', 'Alertas'
        ]
        
        # Formatação e Cores da Tabela
        st.dataframe(
            df_display[cols_view].style.format({
                'Preço Atual': 'R$ {:.2f}',
                'Valor Graham': 'R$ {:.2f}',
                'Valor Bazin': 'R$ {:.2f}',
                'MS Graham (%)': '{:.1f}%',
                'DY (%)': '{:.1f}%',
                'ROE (%)': '{:.1f}%',
                'P/L': '{:.1f}',
                'Score Magic': '{:.0f}'
            }).background_gradient(cmap='Greens', subset=['MS Graham (%)', 'Score Magic', 'ROE (%)']),
            use_container_width=True,
            height=400
        )
        
        st.caption("Nota: 'Score Magic' combina ROE alto com P/L baixo. Quanto maior, melhor.")

        # Gráfico de Dispersão (Visual)
        st.markdown("---")
        col_graph1, col_graph2 = st.columns([2, 1])
        
        with col_graph1:
            st.subheader("📊 Matriz: Qualidade vs. Desconto")
            fig = px.scatter(
                df_display,
                x='MS Graham (%)',
                y='ROE (%)',
                size='DY (%)',       # Tamanho da bolinha = Dividendos
                color='Score Magic', # Cor = Nota Geral
                hover_name='Ticker',
                hover_data=['Preço Atual', 'Valor Graham', 'Alertas'],
                labels={
                    'MS Graham (%)': 'Desconto (Margem de Segurança)', 
                    'ROE (%)': 'Qualidade (Rentabilidade ROE)'
                },
                height=500,
                color_continuous_scale='RdYlGn'
            )
            # Linhas de referência
            fig.add_hline(y=15, line_dash="dot", opacity=0.5, annotation_text="ROE 15%")
            fig.add_vline(x=0, line_dash="dot", opacity=0.5, annotation_text="Preço Justo")
            
            st.plotly_chart(fig, use_container_width=True)
            
        with col_graph2:
            st.info("""
            **Como ler o gráfico:**
            
            🟢 **Canto Superior Direito:** As "Joias". Empresas rentáveis (ROE alto) e baratas (Desconto alto).
            
            🔴 **Canto Inferior Esquerdo:** Empresas caras e pouco rentáveis.
            
            🔵 **Tamanho da Bolinha:** Quanto maior, mais Dividendos (DY) ela paga.
            """)

        # Detalhes Individuais (Raio-X)
        st.markdown("---")
        st.subheader("🔍 Raio-X do Ativo")
        
        opcoes_detalhe = df_display['Ticker'].unique()
        if len(opcoes_detalhe) > 0:
            ticker_select = st.selectbox("Escolha um ativo para ver detalhes:", opcoes_detalhe)
            
            # Pegar dados da linha selecionada
            row = df_display[df_display['Ticker'] == ticker_select].iloc[0]
            
            # Layout de cartões (Agora com CSS corrigido para Dark Mode)
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Preço Atual", f"R$ {row['Preço Atual']:.2f}")
                val_graham = row['Valor Graham']
                st.metric(
                    "Valor Justo (Graham)", 
                    f"R$ {val_graham:.2f}",
                    delta=f"{row['MS Graham (%)']:.1f}% (Margem)",
                    delta_color="normal" # Verde se positivo
                )

            with col2:
                st.metric("Dividend Yield (12m)", f"{row['DY (%)']:.1f}%")
                st.metric(
                    "Teto Bazin (6%)", 
                    f"R$ {row['Valor Bazin']:.2f}",
                    help="Preço máximo para garantir 6% de retorno em dividendos"
                )
                
            with col3:
                st.metric("ROE (Rentabilidade)", f"{row['ROE (%)']:.1f}%")
                
                # Lógica visual para dívida
                divida = row['Dívida/EBITDA']
                if divida > 3:
                    st.metric("Dívida/EBITDA", f"{divida:.2f}x", "Alta", delta_color="inverse")
                else:
                    st.metric("Dívida/EBITDA", f"{divida:.2f}x", "Controlada")

            # Exibir Alertas de Armadilha
            if row['Alertas'] != "OK":
                st.error(f"🚨 **Atenção:** {row['Alertas']}")
            else:
                st.success("✅ **Sinal Verde:** Fundamentos sólidos sem alertas graves.")

if __name__ == "__main__":
    main()
