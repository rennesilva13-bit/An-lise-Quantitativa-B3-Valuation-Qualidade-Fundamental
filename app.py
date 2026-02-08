"""
B3 Pro Analyzer - Titanium Edition (DCF Master)
===============================================
Análise Quantitativa de Ações B3 com Valuation por Fluxo de Caixa Descontado (DCF).
- Projeção de 2 Estágios (Crescimento + Perpetuidade).
- Matriz de Sensibilidade (WACC vs Growth).
- Cálculo automático do Valor Intrínseco para todas as ações.
- Filtros Anti-Trap e Comparação Setorial.

MELHORIAS IMPLEMENTADAS:
- Tratamento robusto de erros e validações
- Otimização de performance
- Melhoria na clareza do código
- Documentação aprimorada
- Correção de bugs potenciais
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import plotly.graph_objects as go
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple, Optional
import time

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
    .main-header { 
        font-size: 2rem; 
        font-weight: bold; 
        color: #0066cc; 
        text-align: center; 
        margin-bottom: 1rem; 
    }
    
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
    
    /* Melhorias de legibilidade */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        border-radius: 4px 4px 0 0;
    }
</style>
""", unsafe_allow_html=True)


class BrapiClient:
    """Cliente para API Brapi.dev com tratamento robusto de dados"""
    
    def __init__(self, token: str = "rxNx6YXRYuEkQFDAc66r3C"):
        self.token = token
        self.base_url = "https://brapi.dev/api"
        
        # Carteira sugerida de ativos com boa liquidez
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

    def _tratar_ticker(self, ticker: str) -> str:
        """Limpa e padroniza o ticker"""
        return ticker.replace("'", "").replace('"', "").strip().upper().replace(".SA", "")

    def _safe_float(self, value) -> float:
        """Converte valor para float de forma segura"""
        try:
            if value is None:
                return 0.0
            val = float(value)
            return val if not np.isnan(val) and np.isfinite(val) else 0.0
        except (ValueError, TypeError):
            return 0.0

    def calcular_rsi(self, precos_historicos: List[float], window: int = 14) -> float:
        """Calcula o Índice de Força Relativa (RSI)"""
        try:
            if not precos_historicos or len(precos_historicos) < window:
                return 50.0
            
            series = pd.Series(precos_historicos)
            delta = series.diff()
            
            gain = delta.where(delta > 0, 0).rolling(window=window).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
            
            # Evita divisão por zero
            loss = loss.replace(0, 0.0001)
            
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            resultado = rsi.iloc[-1]
            return 50.0 if pd.isna(resultado) else float(resultado)
        except Exception:
            return 50.0

    def _buscar_dado(self, stock: Dict, keys_list: List[str]) -> float:
        """Busca um dado na estrutura JSON de forma hierárquica"""
        # Primeiro busca direto
        for k in keys_list:
            if stock.get(k):
                return self._safe_float(stock.get(k))
        
        # Busca em módulos específicos
        modulos = ['defaultKeyStatistics', 'summaryDetail', 'financialData', 'summaryProfile', 'price']
        for mod in modulos:
            if mod in stock and isinstance(stock[mod], dict):
                for k in keys_list:
                    val = stock[mod].get(k)
                    if val is not None:
                        return self._safe_float(val)
        
        return 0.0

    def buscar_ativo_individual(self, ticker_raw: str) -> Optional[Dict]:
        """Busca dados completos de um ativo individual"""
        ticker = self._tratar_ticker(ticker_raw)
        headers = {'Authorization': f'Bearer {self.token}'}
        
        params = {
            'fundamental': 'true', 
            'dividends': 'true',
            'modules': 'defaultKeyStatistics,summaryDetail,financialData,summaryProfile,price',
            'range': '1y',
            'interval': '1d',
        }
        
        try:
            url = f"{self.base_url}/quote/{ticker}"
            response = requests.get(url, headers=headers, params=params, timeout=15)
            
            if response.status_code != 200:
                return None
                
            data = response.json()
            
            if 'results' not in data or not data['results']:
                return None
                
            stock = data['results'][0]
            
            # 1. Dados Básicos
            price = self._safe_float(stock.get('regularMarketPrice'))
            if price <= 0:
                return None
            
            logo = stock.get('logourl', 'https://brapi.dev/favicon.ico')
            
            # Setor com mapeamento para português
            setor = stock.get('summaryProfile', {}).get('sector', 'Outros')
            setor_map = {
                'Financial Services': 'Financeiro', 
                'Utilities': 'Utilidades Púb.',
                'Basic Materials': 'Materiais Básicos', 
                'Energy': 'Energia',
                'Industrials': 'Industrial', 
                'Consumer Defensive': 'Consumo N. Cíclico',
                'Consumer Cyclical': 'Consumo Cíclico', 
                'Technology': 'Tecnologia',
                'Healthcare': 'Saúde', 
                'Real Estate': 'Imobiliário',
                'Communication Services': 'Comunicação'
            }
            setor = setor_map.get(setor, setor)

            # 2. Dados para DCF (Essenciais!)
            fcf = self._buscar_dado(stock, ['freeCashflow', 'freeCashFlow'])
            
            if fcf == 0:
                # Tentativa de cálculo manual: OCF - CapEx
                ocf = self._buscar_dado(stock, ['operatingCashflow', 'totalCashFromOperatingActivities'])
                capex = self._buscar_dado(stock, ['capitalExpenditures'])
                
                if ocf > 0:
                    if capex > 0:
                        fcf = ocf - capex
                    else:
                        # Assumindo 30% de CapEx médio se não houver dado
                        fcf = ocf * 0.7
                else:
                    # Última tentativa: EBITDA * 0.5 (conservador)
                    ebitda = self._buscar_dado(stock, ['ebitda'])
                    if ebitda > 0:
                        fcf = ebitda * 0.5
            
            shares = self._buscar_dado(stock, ['sharesOutstanding', 'impliedSharesOutstanding'])
            total_debt = self._buscar_dado(stock, ['totalDebt'])
            total_cash = self._buscar_dado(stock, ['cash', 'totalCash'])

            # 3. Valuation & Qualidade
            pl = self._buscar_dado(stock, ['priceToEarnings', 'trailingPE'])
            lpa = self._buscar_dado(stock, ['earningsPerShare', 'trailingEps'])
            vpa = self._buscar_dado(stock, ['bookValuePerShare', 'bookValue'])
            pvp = self._buscar_dado(stock, ['priceToBook', 'priceToBookRatio'])
            
            ebitda = self._buscar_dado(stock, ['ebitda'])
            divida_ebitda = self._buscar_dado(stock, ['debtToEbitda'])
            if divida_ebitda == 0 and ebitda > 0 and total_debt > 0:
                divida_ebitda = total_debt / ebitda
            
            margem_liq = self._buscar_dado(stock, ['profitMargins', 'profitMargin'])
            
            # Correções matemáticas
            if vpa == 0 and pvp > 0:
                vpa = price / pvp
            if pvp == 0 and vpa > 0:
                pvp = price / vpa
            if lpa == 0 and pl > 0:
                lpa = price / pl
            if pl == 0 and lpa > 0:
                pl = price / lpa

            # ROE
            roe = self._buscar_dado(stock, ['returnOnEquity'])
            if roe == 0 and lpa > 0 and vpa > 0:
                roe = lpa / vpa
            roe_pct = roe * 100

            # Valor de Graham
            graham = 0.0
            if lpa > 0 and vpa > 0:
                graham = np.sqrt(22.5 * lpa * vpa)

            # Dividend Yield
            dy = self._buscar_dado(stock, ['dividendYield', 'trailingAnnualDividendYield'])
            dy_pct = dy * 100

            # RSI
            hist = stock.get('historicalDataPrice', [])
            precos = [h.get('close', 0) for h in hist if h.get('close')]
            rsi = self.calcular_rsi(precos)

            # 4. Detector de Armadilha de Valor
            armadilha_flags = []
            if pl > 0 and pl < 5:
                armadilha_flags.append("P/L Muito Baixo")
            if divida_ebitda > 5:
                armadilha_flags.append("Dívida Alta")
            if margem_liq < 0:
                armadilha_flags.append("Prejuízo")
            if roe_pct < 5:
                armadilha_flags.append("ROE Baixo")
            
            armadilha = "⚠️ SIM: " + ", ".join(armadilha_flags) if armadilha_flags else "✅ NÃO"

            # 5. Retorno do dicionário
            return {
                'Logo': logo,
                'Ticker': ticker,
                'Setor': setor,
                'Preço': price,
                'P/L': pl,
                'P/VP': pvp,
                'LPA': lpa,
                'VPA': vpa,
                'ROE (%)': roe_pct,
                'V. Graham': graham,
                'DY (%)': dy_pct,
                'Margem Líq (%)': margem_liq * 100,
                'Dívida/EBITDA': divida_ebitda,
                'RSI': rsi,
                'Armadilha': armadilha,
                # Dados DCF
                'FCF': fcf,
                'Shares': shares,
                'Debt': total_debt,
                'Cash': total_cash,
                'Net Debt': total_debt - total_cash,
            }
        except requests.exceptions.Timeout:
            st.warning(f"⏱️ Timeout ao buscar {ticker}")
            return None
        except Exception as e:
            st.warning(f"❌ Erro ao buscar {ticker}: {str(e)[:50]}")
            return None

    def buscar_dados_paralelo(self, tickers: List[str], max_workers: int = 5) -> pd.DataFrame:
        """Busca dados de múltiplos ativos em paralelo"""
        resultados = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ticker = {
                executor.submit(self.buscar_ativo_individual, ticker): ticker 
                for ticker in tickers
            }
            
            for future in as_completed(future_to_ticker):
                try:
                    dado = future.result()
                    if dado:
                        resultados.append(dado)
                except Exception as e:
                    ticker = future_to_ticker[future]
                    st.warning(f"Erro ao processar {ticker}")
        
        if not resultados:
            return pd.DataFrame()
        
        df = pd.DataFrame(resultados)
        return df.sort_values('Ticker').reset_index(drop=True)

    def calcular_magic_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula score de qualidade fundamental (estilo Greenblatt)"""
        if df.empty:
            return df
        
        df_calc = df.copy()
        
        # Normaliza métricas (0-100)
        def normalizar(serie):
            if serie.max() == serie.min():
                return pd.Series([50.0] * len(serie), index=serie.index)
            return ((serie - serie.min()) / (serie.max() - serie.min())) * 100
        
        # ROE alto é bom
        roe_score = normalizar(df_calc['ROE (%)'].clip(lower=0))
        
        # P/L baixo é bom (invertido)
        pl_valid = df_calc['P/L'].replace(0, np.nan).clip(lower=0, upper=50)
        pl_score = 100 - normalizar(pl_valid.fillna(pl_valid.median()))
        
        # RSI próximo de 30-50 é bom (sobrevenda)
        rsi_ideal = np.abs(df_calc['RSI'] - 40)
        rsi_score = 100 - normalizar(rsi_ideal)
        
        # Combina scores
        df_calc['Score Magic'] = (roe_score * 0.4 + pl_score * 0.4 + rsi_score * 0.2).round(1)
        
        return df_calc.sort_values('Score Magic', ascending=False)


def calcular_dcf_individual(
    row: pd.Series, 
    growth_rate: float = 0.06, 
    wacc: float = 0.12, 
    terminal_growth: float = 0.03,
    projection_years: int = 5
) -> Tuple[float, float]:
    """
    Calcula o valor justo por DCF (Discounted Cash Flow) de 2 estágios.
    
    Args:
        row: Linha do DataFrame com dados da empresa
        growth_rate: Taxa de crescimento nos primeiros anos
        wacc: Custo médio ponderado de capital (taxa de desconto)
        terminal_growth: Taxa de crescimento perpétuo
        projection_years: Anos de projeção explícita
    
    Returns:
        Tupla (valor_justo_por_acao, margem_de_seguranca_percentual)
    """
    try:
        fcf = float(row['FCF'])
        shares = float(row['Shares'])
        net_debt = float(row['Net Debt'])
        
        # Validações
        if fcf <= 0 or shares <= 0:
            return 0.0, -100.0
        
        if wacc <= terminal_growth:
            # WACC deve ser maior que crescimento perpétuo
            return 0.0, -100.0
        
        # 1. Projeção de FCF (Crescimento)
        fcf_projetado = []
        for ano in range(1, projection_years + 1):
            fcf_ano = fcf * ((1 + growth_rate) ** ano)
            fcf_projetado.append(fcf_ano)
        
        # 2. Valor Presente dos FCFs
        pv_fcf = 0.0
        for ano, fcf_ano in enumerate(fcf_projetado, start=1):
            pv_fcf += fcf_ano / ((1 + wacc) ** ano)
        
        # 3. Valor Terminal (Perpetuidade)
        fcf_terminal = fcf_projetado[-1] * (1 + terminal_growth)
        terminal_value = fcf_terminal / (wacc - terminal_growth)
        
        # 4. Valor Presente do Terminal Value
        pv_terminal = terminal_value / ((1 + wacc) ** projection_years)
        
        # 5. Enterprise Value
        enterprise_value = pv_fcf + pv_terminal
        
        # 6. Equity Value (descontando dívida líquida)
        equity_value = enterprise_value - net_debt
        
        if equity_value <= 0:
            return 0.0, -100.0
        
        # 7. Valor por Ação
        fair_price = equity_value / shares
        
        # 8. Margem de Segurança
        current_price = float(row['Preço'])
        margin = ((fair_price - current_price) / current_price) * 100
        
        return fair_price, margin
        
    except Exception as e:
        return 0.0, -100.0


def main():
    """Função principal da aplicação"""
    
    st.markdown('<div class="main-header">💎 B3 Pro Analyzer: Titanium Edition (DCF)</div>', unsafe_allow_html=True)
    
    client = BrapiClient()
    
    # Inicializa Session State
    if 'dados_b3' not in st.session_state:
        st.session_state['dados_b3'] = pd.DataFrame()
    if 'ultimo_carregamento' not in st.session_state:
        st.session_state['ultimo_carregamento'] = None

    # === SIDEBAR ===
    st.sidebar.header("⚙️ Painel de Controle")
    
    entrada = st.sidebar.radio("Selecione os Ativos:", ["📊 Carteira Sugerida", "📝 Minha Lista Personalizada"])
    
    if entrada == "📊 Carteira Sugerida":
        tickers = client.tickers_padrao
        st.sidebar.info(f"✅ {len(tickers)} ativos selecionados")
    else:
        texto_tickers = st.sidebar.text_area(
            "Digite os tickers (separados por vírgula):", 
            "WEGE3, VALE3, PRIO3, ITUB4",
            help="Exemplo: PETR4, VALE3, ITUB4"
        )
        if texto_tickers:
            tickers = [t.strip() for t in texto_tickers.split(',') if t.strip()]
        else:
            tickers = []
        
        if tickers:
            st.sidebar.success(f"✅ {len(tickers)} ativos listados")
        else:
            st.sidebar.warning("⚠️ Nenhum ticker definido")

    st.sidebar.divider()
    
    # Configurações Globais DCF
    st.sidebar.subheader("📊 Premissas DCF (Padrão)")
    st.sidebar.caption("Estas premissas serão usadas no ranking geral")
    
    global_wacc = st.sidebar.slider(
        "WACC (Taxa de Desconto) %", 
        min_value=8.0, 
        max_value=20.0, 
        value=12.0, 
        step=0.5,
        help="Custo médio ponderado de capital. Valores típicos: 10-15%"
    ) / 100
    
    global_growth = st.sidebar.slider(
        "Crescimento (5 anos) %", 
        min_value=0.0, 
        max_value=20.0, 
        value=6.0, 
        step=0.5,
        help="Taxa de crescimento esperada do FCF. Seja conservador!"
    ) / 100
    
    st.sidebar.divider()
    
    # Botão de Carregar Dados
    if st.sidebar.button("🚀 Carregar Dados + Calcular DCF", type="primary"):
        if not tickers:
            st.warning("⚠️ Por favor, defina alguns tickers primeiro.")
        else:
            with st.spinner(f"🔍 Analisando {len(tickers)} ativos... Isso pode levar alguns segundos."):
                inicio = time.time()
                
                df_new = client.buscar_dados_paralelo(tickers)
                
                if not df_new.empty:
                    # Calcula Score de Qualidade
                    df_new = client.calcular_magic_score(df_new)
                    
                    # Calcula DCF para todos os ativos
                    st.info("💡 Calculando valuation por DCF...")
                    
                    dcf_results = df_new.apply(
                        lambda x: calcular_dcf_individual(
                            x, 
                            growth_rate=global_growth, 
                            wacc=global_wacc
                        ), 
                        axis=1, 
                        result_type='expand'
                    )
                    
                    df_new['V. DCF (Padrão)'] = dcf_results[0]
                    df_new['MS DCF (%)'] = dcf_results[1]
                    
                    st.session_state['dados_b3'] = df_new
                    st.session_state['ultimo_carregamento'] = time.time()
                    
                    tempo_decorrido = time.time() - inicio
                    st.success(f"✅ Análise concluída em {tempo_decorrido:.1f}s! {len(df_new)} ativos carregados.")
                else:
                    st.error("❌ Não foi possível buscar dados. Verifique os tickers e tente novamente.")

    st.sidebar.divider()
    
    # === FILTROS ===
    st.sidebar.subheader("🔍 Filtros")
    f_armadilha = st.sidebar.checkbox("🚫 Ocultar Armadilhas de Valor", False)
    
    if st.session_state['ultimo_carregamento']:
        tempo_desde = time.time() - st.session_state['ultimo_carregamento']
        minutos = int(tempo_desde / 60)
        st.sidebar.caption(f"⏱️ Última atualização: há {minutos} min")

    # === CONTEÚDO PRINCIPAL ===
    if not st.session_state['dados_b3'].empty:
        df = st.session_state['dados_b3']
        view = df.copy()
        
        # Aplica filtros
        if f_armadilha:
            view = view[view['Armadilha'].str.contains("NÃO", na=False)]
        
        # === TABS ===
        tab1, tab2, tab3 = st.tabs([
            "🏆 Ranking Geral", 
            "🏢 Análise Setorial", 
            "💎 Valuation DCF Detalhado"
        ])
        
        # --- TAB 1: Ranking ---
        with tab1:
            st.subheader("🏆 Melhores Oportunidades (Score + DCF)")
            
            st.info(
                f"📌 **Premissas do DCF:** Crescimento de **{global_growth*100:.1f}%** e "
                f"WACC de **{global_wacc*100:.1f}%**. Para análise personalizada, vá para a aba **'Valuation DCF Detalhado'**."
            )
            
            # Estatísticas Gerais
            col_stats1, col_stats2, col_stats3, col_stats4 = st.columns(4)
            
            with col_stats1:
                st.metric("Total de Ativos", len(view))
            
            with col_stats2:
                oportunidades = len(view[view['MS DCF (%)'] > 20])
                st.metric("Oportunidades (MS > 20%)", oportunidades)
            
            with col_stats3:
                p_l_medio = view[view['P/L'] > 0]['P/L'].median()
                st.metric("P/L Mediano", f"{p_l_medio:.1f}x")
            
            with col_stats4:
                roe_medio = view['ROE (%)'].median()
                st.metric("ROE Mediano", f"{roe_medio:.1f}%")
            
            st.divider()
            
            # Tabela Principal
            cols_view = [
                'Logo', 'Ticker', 'Setor', 'Preço', 'V. Graham', 'V. DCF (Padrão)', 
                'MS DCF (%)', 'P/L', 'ROE (%)', 'DY (%)', 'Score Magic'
            ]
            
            st.dataframe(
                view[cols_view],
                column_config={
                    "Logo": st.column_config.ImageColumn("Logo", width="small"),
                    "Preço": st.column_config.NumberColumn(format="R$ %.2f"),
                    "V. Graham": st.column_config.NumberColumn("V. Graham", format="R$ %.2f"),
                    "V. DCF (Padrão)": st.column_config.NumberColumn("Valor DCF", format="R$ %.2f"),
                    "MS DCF (%)": st.column_config.NumberColumn("Margem Seg.", format="%.1f%%"),
                    "P/L": st.column_config.NumberColumn(format="%.1f"),
                    "ROE (%)": st.column_config.NumberColumn(format="%.1f%%"),
                    "DY (%)": st.column_config.NumberColumn("DY", format="%.2f%%"),
                    "Score Magic": st.column_config.ProgressColumn(
                        "Score", 
                        format="%.0f", 
                        min_value=0, 
                        max_value=100
                    ),
                },
                hide_index=True,
                use_container_width=True,
                height=500
            )
            
            # Gráfico de dispersão P/L vs ROE
            st.divider()
            st.subheader("📊 Mapa de Qualidade: P/L vs ROE")
            
            fig_scatter = px.scatter(
                view[view['P/L'] > 0],
                x='P/L',
                y='ROE (%)',
                size='Score Magic',
                color='MS DCF (%)',
                hover_data=['Ticker', 'Setor'],
                title='Qualidade vs Valuation',
                color_continuous_scale='RdYlGn',
                labels={'P/L': 'P/L (menor é melhor)', 'ROE (%)': 'ROE % (maior é melhor)'}
            )
            fig_scatter.update_layout(height=500)
            st.plotly_chart(fig_scatter, use_container_width=True)
        
        # --- TAB 2: Análise Setorial ---
        with tab2:
            st.subheader("🏢 Comparação por Setor")
            
            setores = sorted(view['Setor'].astype(str).unique())
            setor_sel = st.selectbox("Escolha o Setor:", setores, key='setor_select')
            
            df_setor = view[view['Setor'] == setor_sel].sort_values('Score Magic', ascending=False)
            
            if not df_setor.empty:
                # Métricas do Setor
                col_s1, col_s2, col_s3, col_s4 = st.columns(4)
                
                with col_s1:
                    media_pl = df_setor[df_setor['P/L'] > 0]['P/L'].median()
                    st.metric("P/L Mediano do Setor", f"{media_pl:.1f}x")
                
                with col_s2:
                    media_roe = df_setor['ROE (%)'].median()
                    st.metric("ROE Mediano do Setor", f"{media_roe:.1f}%")
                
                with col_s3:
                    lider = df_setor.iloc[0]['Ticker']
                    st.metric("Líder do Setor (Score)", lider)
                
                with col_s4:
                    total_setor = len(df_setor)
                    st.metric("Ativos no Setor", total_setor)
                
                st.divider()
                
                # Tabela Setorial
                st.dataframe(
                    df_setor[[
                        'Ticker', 'Preço', 'V. DCF (Padrão)', 'MS DCF (%)', 
                        'P/L', 'ROE (%)', 'Dívida/EBITDA', 'Score Magic'
                    ]],
                    column_config={
                        "Preço": st.column_config.NumberColumn(format="R$ %.2f"),
                        "V. DCF (Padrão)": st.column_config.NumberColumn(format="R$ %.2f"),
                        "MS DCF (%)": st.column_config.NumberColumn(format="%.1f%%"),
                        "P/L": st.column_config.NumberColumn(format="%.1f"),
                        "ROE (%)": st.column_config.NumberColumn(format="%.1f%%"),
                        "Dívida/EBITDA": st.column_config.NumberColumn(format="%.2f"),
                        "Score Magic": st.column_config.ProgressColumn(min_value=0, max_value=100),
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                # Gráfico de Barras - Top 10 do Setor
                st.divider()
                st.subheader(f"📊 Top 10 Ativos - {setor_sel}")
                
                top10 = df_setor.head(10).sort_values('Score Magic', ascending=True)
                
                fig_bar = px.bar(
                    top10,
                    x='Score Magic',
                    y='Ticker',
                    orientation='h',
                    title=f'Ranking de Qualidade - {setor_sel}',
                    color='Score Magic',
                    color_continuous_scale='Viridis'
                )
                fig_bar.update_layout(height=400)
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.warning("Nenhum ativo encontrado neste setor.")
        
        # --- TAB 3: DCF DETALHADO ---
        with tab3:
            st.subheader("🔬 Calculadora DCF Profissional (2 Estágios)")
            
            st.info(
                "💡 **Como usar:** Selecione um ativo e ajuste as premissas para ver como o valuation muda. "
                "A matriz de sensibilidade mostra diferentes cenários."
            )
            
            # Seletor de Ativo
            ticker_dcf = st.selectbox(
                "Selecione o Ativo para Análise Detalhada:", 
                view['Ticker'].unique(),
                key='ticker_dcf_select'
            )
            
            row = view[view['Ticker'] == ticker_dcf].iloc[0]
            
            # Layout em 2 colunas
            col_input, col_result = st.columns([1, 2])
            
            with col_input:
                st.markdown("#### 📝 Premissas do Modelo")
                
                dcf_growth = st.slider(
                    "Taxa de Crescimento (5 anos) %", 
                    min_value=0.0, 
                    max_value=25.0, 
                    value=float(global_growth * 100), 
                    step=0.5,
                    help="Taxa anual de crescimento do FCF nos próximos 5 anos",
                    key='growth_slider'
                ) / 100
                
                dcf_wacc = st.slider(
                    "WACC (Taxa de Desconto) %", 
                    min_value=8.0, 
                    max_value=25.0, 
                    value=float(global_wacc * 100), 
                    step=0.5,
                    help="Custo médio ponderado de capital (taxa de desconto)",
                    key='wacc_slider'
                ) / 100
                
                dcf_terminal = st.slider(
                    "Crescimento Perpétuo %", 
                    min_value=0.0, 
                    max_value=6.0, 
                    value=3.0, 
                    step=0.1,
                    help="Taxa de crescimento na perpetuidade (geralmente 2-4%)",
                    key='terminal_slider'
                ) / 100
                
                st.divider()
                
                # Exibe dados da empresa
                st.markdown("#### 📊 Dados Financeiros")
                st.text_input("Ticker", row['Ticker'], disabled=True)
                st.text_input("Setor", row['Setor'], disabled=True)
                
                fcf_milhoes = row['FCF'] / 1e6
                st.number_input(
                    "Fluxo de Caixa Livre (R$ MM)", 
                    value=float(fcf_milhoes), 
                    disabled=True,
                    format="%.2f"
                )
                
                net_debt_milhoes = row['Net Debt'] / 1e6
                st.number_input(
                    "Dívida Líquida (R$ MM)", 
                    value=float(net_debt_milhoes), 
                    disabled=True,
                    format="%.2f"
                )
                
                if row['FCF'] <= 0:
                    st.error("⚠️ FCF não disponível ou negativo. DCF não aplicável.")
            
            with col_result:
                # Recalcula com inputs do usuário
                fair_price, margin = calcular_dcf_individual(
                    row, 
                    growth_rate=dcf_growth, 
                    wacc=dcf_wacc, 
                    terminal_growth=dcf_terminal
                )
                
                st.markdown("### 🎯 Resultado do Valuation")
                
                k1, k2, k3 = st.columns(3)
                
                with k1:
                    st.metric("Preço Atual", f"R$ {row['Preço']:.2f}")
                
                with k2:
                    st.metric("Preço Justo (DCF)", f"R$ {fair_price:.2f}")
                
                with k3:
                    delta_color = "normal" if margin > 0 else "inverse"
                    st.metric(
                        "Upside / Downside", 
                        f"{margin:.1f}%", 
                        delta=f"{margin:.1f}%",
                        delta_color=delta_color
                    )
                
                # Análise do resultado
                if fair_price <= 0:
                    st.error(
                        "⚠️ **Valuation inválido.** O DCF retornou valor negativo ou zero. "
                        "Possíveis causas:\n"
                        "- Fluxo de Caixa Livre (FCF) negativo ou zero\n"
                        "- WACC menor ou igual ao crescimento perpétuo\n"
                        "- Dívida líquida muito alta"
                    )
                else:
                    if margin > 30:
                        st.success("🚀 **FORTE OPORTUNIDADE:** Margem de segurança muito alta! Ativo significativamente subvalorizado.")
                    elif margin > 15:
                        st.success("✅ **BOA OPORTUNIDADE:** Margem de segurança adequada.")
                    elif margin > 0:
                        st.info("⚖️ **PREÇO JUSTO:** Pequeno desconto em relação ao valor intrínseco.")
                    elif margin > -15:
                        st.warning("⚠️ **LEVEMENTE CARO:** Ativo negociando ligeiramente acima do valor justo.")
                    else:
                        st.error("⛔ **MUITO CARO:** Ativo significativamente sobrevalorizado segundo estas premissas.")
                
                st.divider()
                
                # === MATRIZ DE SENSIBILIDADE (HEATMAP) ===
                st.markdown("#### 🔥 Matriz de Sensibilidade: Preço Justo")
                st.caption("Veja como o valuation varia em diferentes cenários de crescimento e WACC")
                
                # Define faixas para análise de sensibilidade
                wacc_range = [
                    max(0.08, dcf_wacc - 0.02),
                    max(0.08, dcf_wacc - 0.01),
                    dcf_wacc,
                    dcf_wacc + 0.01,
                    dcf_wacc + 0.02
                ]
                
                growth_range = [
                    max(0.0, dcf_growth - 0.02),
                    max(0.0, dcf_growth - 0.01),
                    dcf_growth,
                    min(0.25, dcf_growth + 0.01),
                    min(0.25, dcf_growth + 0.02)
                ]
                
                # Calcula matriz de valores
                z_values = []
                for w in wacc_range:
                    row_z = []
                    for g in growth_range:
                        fp, _ = calcular_dcf_individual(row, g, w, dcf_terminal)
                        row_z.append(round(fp, 2))
                    z_values.append(row_z)
                
                # Cria heatmap
                fig_heat = px.imshow(
                    z_values,
                    labels=dict(x="Crescimento (Growth)", y="WACC", color="Preço Justo (R$)"),
                    x=[f"{g*100:.1f}%" for g in growth_range],
                    y=[f"{w*100:.1f}%" for w in wacc_range],
                    text_auto=True,
                    color_continuous_scale='RdYlGn',
                    aspect='auto'
                )
                
                fig_heat.update_layout(
                    height=450,
                    title=f"Sensibilidade do Valuation - {ticker_dcf}"
                )
                
                st.plotly_chart(fig_heat, use_container_width=True)
                
                st.caption(
                    "📊 **Como ler:** Valores mais altos (verde) indicam maior valuation. "
                    "A célula central representa o cenário base com suas premissas atuais."
                )
    
    else:
        # Estado inicial - sem dados carregados
        st.info(
            "👈 **Bem-vindo ao B3 Pro Analyzer!**\n\n"
            "Para começar:\n"
            "1. Escolha entre a carteira sugerida ou insira seus próprios tickers\n"
            "2. Ajuste as premissas de DCF conforme sua análise\n"
            "3. Clique em '🚀 Carregar Dados + Calcular DCF'\n\n"
            "A análise incluirá valuation por Graham e DCF, além de métricas de qualidade fundamental."
        )
        
        # Exibe exemplo de análise
        with st.expander("📚 Entenda as Métricas"):
            st.markdown("""
            **Métricas Principais:**
            
            - **P/L (Preço/Lucro):** Quanto você paga por cada R$ 1 de lucro. Valores baixos podem indicar oportunidade.
            - **ROE (Return on Equity):** Rentabilidade sobre o patrimônio. Acima de 15% é considerado bom.
            - **V. Graham:** Valor intrínseco pela fórmula de Benjamin Graham.
            - **V. DCF:** Valor intrínseco por Fluxo de Caixa Descontado (2 estágios).
            - **MS DCF (%):** Margem de Segurança - diferença percentual entre preço justo e preço de mercado.
            - **Score Magic:** Pontuação de qualidade de 0-100 baseada em múltiplas métricas.
            
            **Detector de Armadilhas:**
            Identifica ações que parecem baratas mas podem ter problemas fundamentais (alta dívida, prejuízo, etc).
            """)

if __name__ == "__main__":
    main()
