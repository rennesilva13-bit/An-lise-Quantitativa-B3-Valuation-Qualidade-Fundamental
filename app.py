"""
B3 Pro Analyzer - Brapi Edition (Final)
=======================================
- Autenticação via Header (Padrão Oficial)
- Parâmetro dividends=true ativado
- Slider de Margem Graham ajustado (0 a 100)
- Token Integrado: rxNx6YXRYuEkQFDAc66r3C

Autor: Analista Quantitativo
Data: 2026
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import warnings

# Ignorar avisos de depreciação
warnings.filterwarnings('ignore')

# --- Configuração da Página ---
st.set_page_config(
    page_title="B3 Pro Valuation",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS Customizado (Visual Clean) ---
st.markdown("""
<style>
    .main-header { font-size: 2rem; font-weight: bold; color: #0066cc; text-align: center; margin-bottom: 1rem; }
    
    /* Cards de Métricas */
    div[data-testid="stMetric"] {
        background-color: #ffffff !important;
        border-radius: 10px; padding: 15px; 
        border: 1px solid #e0e0e0;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    div[data-testid="stMetric"] label { color: #555 !important; font-size: 0.9rem !important; }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] { color: #000 !important; font-weight: bold !important; }
    
    /* Imagens (Logos) */
    img { border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

class BrapiClient:
    """Cliente oficial para conectar com a Brapi.dev seguindo a documentação."""
    
    def __init__(self):
        # TOKEN INTEGRADO
        self.token = "rxNx6YXRYuEkQFDAc66r3C"
        self.base_url = "https://brapi.dev/api"
        
        # Lista padrão para monitoramento rápido
        self.tickers_padrao = [
            'BBAS3', 'ITUB4', 'BBDC4', 'SANB11', 'TAEE11', 'TRPL4', 'CPLE6', 'EGIE3',
            'VALE3', 'CSNA3', 'GGBR4', 'WEGE3', 'PSSA3', 'BBSE3', 'CXSE3', 'SAPR11',
            'CMIG4', 'KLBN11', 'SUZB3', 'PRIO3', 'PETR4', 'JBSS3', 'MRFG3', 'GOAU4'
        ]

    def _tratar_lista_tickers(self, tickers_list):
        """Limpa a lista de tickers removendo caracteres indesejados."""
        clean_list = []
        for t in tickers_list:
            # Remove aspas, vírgulas extras e espaços
            t_clean = t.replace("'", "").replace('"', "").replace(",", "").replace(";", "").strip().upper()
            if t_clean:
                # Remove o sufixo .SA se existir (a API aceita ambos, mas sem é mais limpo)
                t_clean = t_clean.replace(".SA", "")
                clean_list.append(t_clean)
        return clean_list

    def calcular_rsi(self, precos_historicos, window=14):
        """Calcula o IFR (RSI) de 14 períodos com tratamento de erro."""
        try:
            if not precos_historicos or len(precos_historicos) < window: 
                return 50 # Retorna neutro se não houver dados suficientes
            
            series = pd.Series(precos_historicos)
            delta = series.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
            
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            resultado = rsi.iloc[-1]
            if pd.isna(resultado): return 50
            return resultado
        except:
            return 50

    def buscar_dados_batch(self, tickers):
        """
        Busca dados de múltiplos ativos usando as melhores práticas da Brapi:
        - Auth via Header
        - Params: fundamental=true, dividends=true
        """
        tickers_limpos = self._tratar_lista_tickers(tickers)
        if not tickers_limpos: return pd.DataFrame()

        tickers_str = ",".join(tickers_limpos)
        
        # --- CONFIGURAÇÃO DA REQUISIÇÃO ---
        headers = {
            'Authorization': f'Bearer {self.token}'
        }
        
        params = {
            'fundamental': 'true', # Traz P/L, LPA, VPA, etc.
            'dividends': 'true',   # Traz dados de proventos
            'range': '1mo',        # Histórico para o gráfico/RSI
            'interval': '1d',
        }
        
        try:
            url = f"{self.base_url}/quote/{tickers_str}"
            response = requests.get(url, headers=headers, params=params, timeout=20)
            
            if response.status_code != 200:
                st.error(f"Erro na API (Status {response.status_code}): {response.text}")
                return pd.DataFrame()
                
            data = response.json()
            
            if 'results' not in data:
                return pd.DataFrame()
            
            resultados = []
            
            for stock in data['results']:
                try:
                    # Dados Básicos
                    ticker = stock.get('symbol', 'N/A')
                    price = stock.get('regularMarketPrice')
                    
                    if price is None or price == 0:
                        continue
                        
                    logo = stock.get('logourl', 'https://brapi.dev/favicon.ico')
                    
                    # --- Fundamentos ---
                    # Tenta pegar diretamente da raiz ou substitui por 0
                    pl = stock.get('priceToEarnings', 0) or 0
                    lpa = stock.get('earningsPerShare', 0) or 0
                    
                    # VPA (Valor Patrimonial por Ação)
                    vpa = stock.get('bookValuePerShare', 0) or 0
                    if vpa == 0: 
                         vpa = stock.get('bookValue', 0) or 0

                    # Dividendos
                    dy_raw = stock.get('dividendYield', 0) or 0
                    # Correção: Se vier > 1 (ex: 6.5), é percentual. Se < 1 (ex: 0.065), é decimal.
                    dy_decimal = dy_raw / 100 if dy_raw > 1 else dy_raw
                    
                    # ROE e Liquidez
                    roe = stock.get('returnOnEquity', 0) or 0
                    volume = stock.get('regularMarketVolume', 0) or 0
                    
                    # --- Cálculos de Valuation ---
                    
                    # 1. Fórmula de Graham (Raiz de 22.5 * LPA * VPA)
                    valor_graham = 0
                    ms_graham = 0
                    if lpa > 0 and vpa > 0:
                        valor_graham = np.sqrt(22.5 * lpa * vpa)
                        # Margem de Segurança: (Valor Justo - Preço) / Preço
                        ms_graham = ((valor_graham - price) / price) * 100
                    else:
                        ms_graham = -999 # Sem dados suficientes

                    # 2. Método Bazin (Preço Teto = Dividendos / 6%)
                    dy_reais = price * dy_decimal
                    valor_bazin = dy_reais / 0.06 if dy_reais > 0 else 0
                    
                    # 3. IFR (Técnico)
                    rsi = 50
                    hist = stock.get('historicalDataPrice', [])
                    if hist:
                        closes = [d.get('close') for d in hist if d.get('close')]
                        rsi = self.calcular_rsi(closes)
                    
                    # --- Filtro de Armadilhas ---
                    motivo_trap = []
                    is_trap = False
                    
                    # Regra 1: ROE muito baixo (empresa ineficiente)
                    if roe != 0 and roe < 0.05: 
                        motivo_trap.append("ROE Baixo")
                    
                    # Regra 2: Liquidez baixa (difícil sair do papel)
                    if volume < 100000: 
                        motivo_trap.append("Liquidez Baixa")
                    
                    if motivo_trap: is_trap = True

                    resultados.append({
                        'Logo': logo,
                        'Ticker': ticker,
                        'Preço': price,
                        'V. Graham': valor_graham,
                        'V. Bazin': valor_bazin,
                        'MS Graham (%)': ms_graham,
                        'DY (%)': dy_decimal * 100,
                        'P/L': pl,
                        'ROE (%)': roe * 100,
                        'IFR (14)': rsi,
                        'Armadilha': "⚠️ SIM" if is_trap else "🛡️ NÃO",
                        'Alertas': ", ".join(motivo_trap) if motivo_trap else "OK",
                        'Score Magic': 0 # Será calculado na sequência
                    })
                    
                except Exception as e:
                    print(f"Erro processando {stock.get('symbol')}: {e}")
                    continue
            
            return pd.DataFrame(resultados)
            
        except Exception as e:
            st.error(f"Erro fatal de conexão: {e}")
            return pd.DataFrame()

    def calcular_magic_score(self, df):
        """Cria um ranking combinando Qualidade (ROE) e Preço (P/L)."""
        if df.empty: return df
        df = df.copy()
        
        # Filtra apenas empresas com lucro (P/L positivo) para o ranking
        mask = df['P/L'] > 0
        if not mask.any(): return df

        # Rank P/L: Menor é melhor (Ascending=True)
        df.loc[mask, 'Rank_PL'] = df.loc[mask, 'P/L'].rank(ascending=True)
        
        # Rank ROE: Maior é melhor (Ascending=False)
        # Se ROE for 0, joga para o final
        df.loc[mask, 'Rank_ROE'] = df.loc[mask, 'ROE (%)'].replace(0, -999).rank(ascending=False)
        
        # Soma dos Ranks (Menor soma = Melhor empresa)
        df['Magic_Points'] = df['Rank_PL'] + df['Rank_ROE']
        
        # Normaliza para Score 0 a 100
        min_p, max_p = df['Magic_Points'].min(), df['Magic_Points'].max()
        
        if max_p != min_p:
            df['Score Magic'] = 100 * (1 - (df['Magic_Points'] - min_p) / (max_p - min_p))
        else:
            df['Score Magic'] = 50
            
        return df.sort_values('Score Magic', ascending=False).fillna(0)

def main():
    st.markdown('<div class="main-header">💎 B3 Pro: Brapi Edition</div>', unsafe_allow_html=True)
    
    client = BrapiClient()
    
    # --- SIDEBAR ---
    st.sidebar.header("⚙️ Painel de Controle")
    entrada = st.sidebar.radio("Seleção de Ativos:", ["Carteira Sugerida (Bancos/Elétricas/Commodities)", "Minha Lista Personalizada"])
    
    if entrada == "Carteira Sugerida (Bancos/Elétricas/Commodities)":
        tickers = client.tickers_padrao
        st.sidebar.info(f"Monitorando {len(tickers)} ativos principais.")
    else:
        text = st.sidebar.text_area("Digite os tickers (separados por vírgula):", "PETR4, VALE3, WEGE3, ITUB4")
        if text:
            tickers = text.split(',')
        else:
            tickers = []

    st.sidebar.divider()
    
    # --- FILTROS ---
    st.sidebar.subheader("Filtros de Segurança")
    f_armadilha = st.sidebar.checkbox("Ocultar 'Armadilhas' (ROE Baixo / Sem Liquidez)", value=False)
    
    # SLIDER AJUSTADO: 0 a 100 conforme solicitado
    min_ms = st.sidebar.slider(
        "Margem Graham Mínima %", 
        min_value=0, 
        max_value=100, 
        value=0,
        help="Filtra empresas que não tenham pelo menos X% de desconto em relação ao Valor de Graham."
    )
    
    # --- PROCESSAMENTO ---
    if st.sidebar.button("🚀 Processar Análise"):
        if not tickers:
            st.warning("Por favor, defina os tickers para análise.")
            return
            
        with st.spinner("Conectando à B3 via Brapi.dev..."):
            df = client.buscar_dados_batch(tickers)
        
        if df.empty:
            st.error("❌ Não foi possível obter dados. Verifique os tickers ou a conexão.")
            st.info("Dica: Tente usar a 'Carteira Sugerida' para testar.")
            return

        # Calcula o Ranking Magic
        df = client.calcular_magic_score(df)
        
        # Aplica Filtros Visuais
        view = df.copy()
        
        if f_armadilha:
            view = view[view['Armadilha'].str.contains("NÃO")]
        
        # Aplica o filtro do Slider (0 a 100)
        view = view[view['MS Graham (%)'] >= min_ms]

        # --- DASHBOARD ---
        st.subheader(f"🎯 Resultados Filtrados ({len(view)} ativos)")
        
        if view.empty:
            st.warning(f"Nenhuma ação atende ao critério de Margem de Graham >= {min_ms}%. Tente diminuir o filtro.")
        else:
            # Tabela Principal
            st.dataframe(
                view[['Logo', 'Ticker', 'Preço', 'V. Graham', 'MS Graham (%)', 'DY (%)', 'P/L', 'ROE (%)', 'IFR (14)', 'Score Magic', 'Alertas']],
                column_config={
                    "Logo": st.column_config.ImageColumn("Logo", width="small"),
                    "Preço": st.column_config.NumberColumn(format="R$ %.2f"),
                    "V. Graham": st.column_config.NumberColumn(format="R$ %.2f"),
                    "MS Graham (%)": st.column_config.NumberColumn(format="%.1f%%"),
                    "DY (%)": st.column_config.NumberColumn(format="%.1f%%"),
                    "Score Magic": st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100),
                },
                hide_index=True,
                use_container_width=True,
                height=500
            )

            st.divider()
            
            # Gráficos
            col1, col2 = st.columns([3, 1])
            with col1:
                st.subheader("📊 Gráfico de Oportunidades")
                fig = px.scatter(
                    view, x='MS Graham (%)', y='ROE (%)', 
                    size='Preço', 
                    color='Score Magic', 
                    hover_name='Ticker',
                    hover_data=['Preço', 'Alertas'],
                    color_continuous_scale='RdYlGn',
                    labels={'MS Graham (%)': 'Desconto Graham (%)', 'ROE (%)': 'Qualidade ROE (%)'},
                    height=450
                )
                fig.add_vline(x=0, line_dash="dot", annotation_text="Preço Justo")
                st.plotly_chart(fig, use_container_width=True)
                
            with col2:
                st.info("""
                **Legenda:**
                
                🟢 **Verde Escuro:** Score Magic Alto (Barata + Rentável).
                
                📏 **Eixo X:** Quanto mais à direita, maior o desconto (Graham).
                
                👆 **Eixo Y:** Quanto mais ao alto, maior a qualidade (ROE).
                """)

            # Raio-X Individual
            st.divider()
            sel = st.selectbox("🔍 Detalhar Ativo:", view['Ticker'].unique())
            if sel:
                r = view[view['Ticker'] == sel].iloc[0]
                
                # Header com Logo
                c_img, c_info = st.columns([1, 6])
                with c_img:
                    if r['Logo']: st.image(r['Logo'], width=80)
                with c_info:
                    st.markdown(f"## {r['Ticker']}")
                    st.caption(f"Cotação Atual: R$ {r['Preço']:.2f}")

                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Valor Justo (Graham)", f"R$ {r['V. Graham']:.2f}")
                k2.metric("Teto Bazin (6%)", f"R$ {r['V. Bazin']:.2f}")
                k3.metric("IFR (14)", f"{r['IFR (14)']:.0f}", "Sobrecomprado" if r['IFR (14)'] > 70 else "Neutro")
                k4.metric("ROE", f"{r['ROE (%)']:.1f}%")

if __name__ == "__main__":
    main()
