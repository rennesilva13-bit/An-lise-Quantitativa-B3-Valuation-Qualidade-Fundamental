"""
B3 Pro Analyzer - Brapi Edition (Robust)
========================================
Versão atualizada com tratamento de erros avançado.
Se um dado faltar (ex: P/L), o sistema preenche com 0 mas não esconde a ação.

Token Atualizado: rxNx6YXRYuEkQFDAc66r3C
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import warnings

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
    
    /* Cards de Métricas */
    div[data-testid="stMetric"] {
        background-color: #ffffff !important;
        border-radius: 10px; padding: 15px; 
        border: 1px solid #e0e0e0;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    div[data-testid="stMetric"] label { color: #555 !important; font-size: 0.9rem !important; }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] { color: #000 !important; font-weight: bold !important; }
    
    /* Imagem do Logo */
    img { border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

class BrapiClient:
    """Cliente oficial para conectar com a Brapi.dev"""
    
    def __init__(self):
        # NOVA CHAVE
        self.token = "rxNx6YXRYuEkQFDAc66r3C"
        self.base_url = "https://brapi.dev/api"
        
        self.tickers_padrao = [
            'BBAS3', 'ITUB4', 'BBDC4', 'SANB11', 'TAEE11', 'TRPL4', 'CPLE6', 'EGIE3',
            'VALE3', 'CSNA3', 'GGBR4', 'WEGE3', 'PSSA3', 'BBSE3', 'CXSE3', 'SAPR11',
            'CMIG4', 'KLBN11', 'SUZB3', 'PRIO3', 'PETR4', 'JBSS3', 'MRFG3', 'GOAU4'
        ]

    def _tratar_lista_tickers(self, tickers_list):
        """Limpa a lista de tickers"""
        clean_list = []
        for t in tickers_list:
            # Remove caracteres estranhos
            t_clean = t.replace("'", "").replace('"', "").replace(",", "").replace(";", "").strip().upper()
            if t_clean:
                # Brapi aceita com ou sem .SA, mas sem é mais seguro para o match
                t_clean = t_clean.replace(".SA", "")
                clean_list.append(t_clean)
        return clean_list

    def calcular_rsi(self, precos_historicos, window=14):
        """Calcula IFR (RSI) com segurança (retorna 50 se falhar)"""
        try:
            if not precos_historicos or len(precos_historicos) < window: 
                return 50
            
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
        """Busca dados com tratamento de erro individual por ativo."""
        tickers_limpos = self._tratar_lista_tickers(tickers)
        if not tickers_limpos: return pd.DataFrame()

        tickers_str = ",".join(tickers_limpos)
        
        # Parâmetros otimizados para evitar timeouts
        params = {
            'token': self.token,
            'fundamental': 'true', 
            'range': '1mo',
            'interval': '1d',
        }
        
        try:
            # st.write(f"Debug: Consultando {tickers_str}...") # Descomente se precisar debug
            response = requests.get(f"{self.base_url}/quote/{tickers_str}", params=params, timeout=15)
            
            if response.status_code != 200:
                st.error(f"Erro na API (Status {response.status_code}): {response.text}")
                return pd.DataFrame()
                
            data = response.json()
            
            if 'results' not in data:
                # Verifica se veio mensagem de erro
                if 'message' in data:
                    st.warning(f"Aviso da API: {data['message']}")
                return pd.DataFrame()
            
            resultados = []
            
            for stock in data['results']:
                # Bloco de segurança: Se um cálculo falhar, a ação ainda aparece na lista
                try:
                    ticker = stock.get('symbol', 'N/A')
                    price = stock.get('regularMarketPrice')
                    
                    # Se não tem preço, nem adianta mostrar
                    if price is None or price == 0:
                        continue
                        
                    logo = stock.get('logourl', 'https://brapi.dev/favicon.ico')
                    
                    # --- Fundamentos (com valores padrão 0) ---
                    pl = stock.get('priceToEarnings', 0) or 0
                    lpa = stock.get('earningsPerShare', 0) or 0
                    
                    # Tenta pegar VPA (pode vir com nomes diferentes)
                    vpa = stock.get('bookValuePerShare', 0) or 0
                    if vpa == 0: # Tenta fallback
                         vpa = stock.get('bookValue', 0) or 0

                    # Dividendos
                    dy_raw = stock.get('dividendYield', 0) or 0
                    # Correção de escala (se vier 6.5 é %, se vier 0.065 é decimal)
                    dy_decimal = dy_raw / 100 if dy_raw > 1 else dy_raw
                    
                    # ROE (Pode falhar no plano free)
                    roe = stock.get('returnOnEquity', 0) or 0
                    
                    # --- Cálculos ---
                    
                    # Graham
                    valor_graham = 0
                    ms_graham = 0
                    if lpa > 0 and vpa > 0:
                        valor_graham = np.sqrt(22.5 * lpa * vpa)
                        ms_graham = ((valor_graham - price) / price) * 100
                    else:
                        ms_graham = -999 # Código para "Sem dados"

                    # Bazin
                    dy_reais = price * dy_decimal
                    valor_bazin = dy_reais / 0.06 if dy_reais > 0 else 0
                    
                    # IFR (RSI)
                    rsi = 50
                    hist = stock.get('historicalDataPrice', [])
                    if hist:
                        closes = [d.get('close') for d in hist if d.get('close')]
                        rsi = self.calcular_rsi(closes)
                    
                    # Armadilhas
                    motivo_trap = []
                    is_trap = False
                    
                    # Só critica se o dado existir (!=0)
                    if roe != 0 and roe < 0.05: motivo_trap.append("ROE Baixo")
                    if stock.get('regularMarketVolume', 999999) < 100000: motivo_trap.append("Liquidez Baixa")
                    
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
                        'Score Magic': 0
                    })
                    
                except Exception as e:
                    # Se der erro numa ação específica, loga mas não para o app
                    print(f"Erro processando {stock.get('symbol')}: {e}")
                    continue
            
            return pd.DataFrame(resultados)
            
        except Exception as e:
            st.error(f"Erro fatal de conexão: {e}")
            return pd.DataFrame()

    def calcular_magic_score(self, df):
        if df.empty: return df
        df = df.copy()
        
        # Filtra apenas quem tem dados mínimos de P/L para o ranking
        mask = df['P/L'] > 0
        if not mask.any(): return df

        df.loc[mask, 'Rank_PL'] = df.loc[mask, 'P/L'].rank(ascending=True)
        
        # Se ROE for 0, joga pro fim da fila, mas não remove
        df.loc[mask, 'Rank_ROE'] = df.loc[mask, 'ROE (%)'].replace(0, -999).rank(ascending=False)
        
        df['Magic_Points'] = df['Rank_PL'] + df['Rank_ROE']
        min_p, max_p = df['Magic_Points'].min(), df['Magic_Points'].max()
        
        if max_p != min_p:
            df['Score Magic'] = 100 * (1 - (df['Magic_Points'] - min_p) / (max_p - min_p))
        else:
            df['Score Magic'] = 50
            
        return df.sort_values('Score Magic', ascending=False).fillna(0)

def main():
    st.markdown('<div class="main-header">💎 B3 Pro: Brapi Edition</div>', unsafe_allow_html=True)
    
    client = BrapiClient()
    
    # Sidebar
    st.sidebar.header("⚙️ Controle")
    entrada = st.sidebar.radio("Ativos:", ["Carteira Monitorada", "Minha Lista"])
    
    if entrada == "Carteira Monitorada":
        tickers = client.tickers_padrao
        st.sidebar.info(f"Monitorando {len(tickers)} ativos.")
    else:
        text = st.sidebar.text_area("Digite os tickers:", "CMIG4, PETR4, VALE3")
        if text:
            tickers = text.split(',')
        else:
            tickers = []

    st.sidebar.divider()
    f_armadilha = st.sidebar.checkbox("Ocultar 'Armadilhas'", False) # Padrão False para ver tudo agora
    min_ms = st.sidebar.slider("Margem Graham Mínima %", -100, 100, -50) # Padrão permissivo
    
    if st.sidebar.button("🚀 Consultar API"):
        if not tickers:
            st.warning("Defina os tickers.")
            return
            
        with st.spinner("Consultando Brapi.dev..."):
            df = client.buscar_dados_batch(tickers)
        
        if df.empty:
            st.error("❌ Nenhum dado retornado. Verifique se o ticker existe ou se a API está online.")
            # Dica de Debug
            st.info("Dica: Tente um ticker simples como 'PETR4' para testar.")
            return

        # Calcula Ranking
        df = client.calcular_magic_score(df)
        
        # Filtros Visuais
        view = df.copy()
        if f_armadilha:
            view = view[view['Armadilha'].str.contains("NÃO")]
        
        # Filtro de Graham (Só aplica se tiver Graham calculado, senão ignora)
        view = view[view['MS Graham (%)'] >= min_ms]

        # Dashboard
        st.subheader(f"🎯 Resultado ({len(view)} ativos)")
        
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
        
        # Só mostra gráficos se tiver dados
        if not view.empty:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.subheader("📊 Gráfico de Valor")
                fig = px.scatter(
                    view, x='MS Graham (%)', y='ROE (%)', 
                    size='Preço', # Tamanho fixo ou baseado no preço para não sumir
                    color='Score Magic', 
                    hover_name='Ticker',
                    hover_data=['Preço', 'Alertas'],
                    color_continuous_scale='RdYlGn',
                    height=400
                )
                fig.add_vline(x=0, line_dash="dot", annotation_text="Preço Justo")
                st.plotly_chart(fig, use_container_width=True)
                
            with col2:
                st.info("Se o 'Valor Graham' estiver zerado, significa que a API não forneceu LPA/VPA suficientes para o cálculo.")

            # Detalhe Visual
            st.divider()
            sel = st.selectbox("Raio-X do Ativo:", view['Ticker'].unique())
            if sel:
                r = view[view['Ticker'] == sel].iloc[0]
                
                c_img, c_info = st.columns([1, 5])
                with c_img:
                    if r['Logo']: st.image(r['Logo'], width=80)
                with c_info:
                    st.markdown(f"## {r['Ticker']}")
                    st.markdown(f"**Preço:** R$ {r['Preço']:.2f}")

                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Valor Graham", f"R$ {r['V. Graham']:.2f}")
                k2.metric("Valor Bazin", f"R$ {r['V. Bazin']:.2f}")
                k3.metric("IFR (14)", f"{r['IFR (14)']:.0f}")
                k4.metric("ROE", f"{r['ROE (%)']:.1f}%")

if __name__ == "__main__":
    main()
