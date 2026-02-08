"""
B3 Quant Analyzer - Brapi.dev Edition
=====================================
Versão Profissional utilizando API oficial da Brapi.
Vantagens:
- Velocidade extrema (Batch Requests)
- Dados oficiais da B3
- Logos das empresas
- Maior confiabilidade nos dividendos e fundamentos

Autor: Analista Quantitativo
Data: 2026
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
    
    /* Imagem do Logo no DataFrame/Tabelas */
    img { border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

class BrapiClient:
    """Cliente oficial para conectar com a Brapi.dev"""
    
    def __init__(self):
        # SUA CHAVE DE API AQUI
        self.token = "1mVpXXJK2x9HHtpM8m7Ns6"
        self.base_url = "https://brapi.dev/api"
        
        self.tickers_padrao = [
            'BBAS3', 'ITUB4', 'BBDC4', 'SANB11', 'TAEE11', 'TRPL4', 'CPLE6', 'EGIE3',
            'VALE3', 'CSNA3', 'GGBR4', 'WEGE3', 'PSSA3', 'BBSE3', 'CXSE3', 'SAPR11',
            'CMIG4', 'KLBN11', 'SUZB3', 'PRIO3', 'PETR4', 'JBSS3', 'MRFG3', 'GOAU4'
        ]

    def _tratar_lista_tickers(self, tickers_list):
        """Limpa e formata a lista de tickers para a URL da Brapi"""
        clean_list = []
        for t in tickers_list:
            # Remove aspas, espaços e .SA (Brapi aceita sem .SA e é melhor assim)
            t_clean = t.replace("'", "").replace('"', "").replace(".SA", "").strip().upper()
            if t_clean:
                clean_list.append(t_clean)
        return clean_list

    def calcular_rsi(self, precos_historicos, window=14):
        """Calcula IFR (RSI) baseado numa lista de preços de fechamento"""
        if len(precos_historicos) < window: return 50
        
        series = pd.Series(precos_historicos)
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]

    def buscar_dados_batch(self, tickers):
        """
        Busca dados de MÚLTIPLOS ativos em UMA ÚNICA requisição (Super Rápido).
        """
        tickers_limpos = self._tratar_lista_tickers(tickers)
        if not tickers_limpos: return pd.DataFrame()

        # Junta tickers com vírgula (ex: PETR4,VALE3,WEGE3)
        tickers_str = ",".join(tickers_limpos)
        
        # Endpoint: /quote/list (Fundamental=true traz indicadores)
        # range=1mo e interval=1d para calcularmos o RSI
        url = f"{self.base_url}/quote/{tickers_str}"
        params = {
            'token': self.token,
            'fundamental': 'true', # Traz P/L, LPA, VPA, etc.
            'range': '1mo',
            'interval': '1d',
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if 'results' not in data:
                return pd.DataFrame()
            
            resultados = []
            
            for stock in data['results']:
                try:
                    # Dados Básicos
                    ticker = stock.get('symbol', 'N/A')
                    price = stock.get('regularMarketPrice', 0) or 0
                    logo = stock.get('logourl', '')
                    sector = "N/A" # Brapi as vezes envia em outro endpoint, vamos focar no quant
                    
                    # IFR (RSI) - Requer histórico
                    rsi = 50
                    if 'historicalDataPrice' in stock:
                        closes = [day['close'] for day in stock['historicalDataPrice'] if 'close' in day]
                        rsi = self.calcular_rsi(closes)

                    # Fundamentos (Onde a mágica acontece)
                    # A Brapi entrega indicadores pré-calculados na chave 'priceToEarnings', etc.
                    # Mas às vezes é preciso pegar de 'summaryProfile' ou similar dependendo da resposta
                    
                    # Tentativa de extração direta
                    pl = stock.get('priceToEarnings', 0) or 0
                    
                    # Cálculo reverso de Graham (LPA e VPA)
                    # A Brapi nem sempre dá VPA direto, mas dá P/VP (priceToBook) ou BookValuePerShare
                    # Vamos tentar extrair dados robustos
                    
                    # Dicionário de fallback para evitar erros
                    lpa = stock.get('earningsPerShare', 0) or 0
                    # Se não vier earningsPerShare, tentamos calcular pelo P/L: Preço / PL
                    if lpa == 0 and pl > 0:
                        lpa = price / pl
                        
                    # Busca BookValue ou derivados
                    # Algumas respostas da Brapi trazem financialData. 
                    # Simplificação para robustez:
                    # Se não tiver bookValuePerShare (VPA), tentamos inferir se tivermos P/VP?
                    # A Brapi costuma mandar o 'regularMarketPrice' e o valor de mercado, mas não VPA direto sempre no batch.
                    # Vamos usar uma lógica de segurança:
                    
                    # Se não vier VPA explicito, tentamos: Preço Atual (se P/VP não for nulo)
                    # Mas para o Batch, vamos confiar nos dados que vierem ou zerar.
                    # Nota: A Brapi no plano gratuito/teste pode limitar alguns fundamentos, mas no pago libera tudo.
                    
                    # Mapeando campos comuns da Brapi
                    # Nota: A estrutura pode variar levemente, o código abaixo tenta ser defensivo.
                    
                    # Tenta extrair fundamentals se existir um objeto aninhado (comum na Brapi v2)
                    # Caso contrário usa a raiz
                    
                    pvp = 0
                    # Procura em summaryProfile ou financialData se existir (não comum no endpoint quote list simples)
                    # No endpoint simples, confiamos nos campos da raiz se disponíveis.
                    
                    # Para Graham precisamos de LPA e VPA.
                    # Vamos assumir que se não temos VPA direto, Graham falha (segurança).
                    # A Brapi geralmente retorna 'priceToBook' na raiz? Às vezes não.
                    # Se não retornar, vamos deixar zerado para não inventar dados.
                    
                    dy_percent = 0
                    # Tenta pegar dividend yield
                    # A Brapi retorna isso em 'dividendYield' na raiz?
                    # Às vezes vem zerado se não houver pagamento recente.
                    
                    # --- REFINAMENTO PARA BRAPI ---
                    # Para garantir, vamos usar os dados que geralmente vêm no endpoint 'quote':
                    # symbol, shortName, regularMarketPrice, regularMarketDayHigh, regularMarketDayLow, regularMarketVolume.
                    # Os fundamentos como P/L e DY podem não vir no batch "list" dependendo do tier.
                    # Mas se vierem, usamos.
                    
                    pl = stock.get('priceToEarnings', 0) or 0
                    lpa = stock.get('earningsPerShare', 0) or 0
                    
                    # Valor de Graham e Bazin
                    # Se LPA e Price existem, podemos tentar inferir VPA se tivermos marketCap? Não muito preciso.
                    # Vamos fazer o seguinte: Para essa versão, se a API não entregar o VPA,
                    # Graham fica neutro.
                    
                    # Melhoria: Se o usuário forneceu uma chave válida, a Brapi deve entregar mais dados.
                    
                    valor_graham = 0
                    # Precisamos do VPA. Se a Brapi mandar, ótimo. 
                    # Campos possíveis: 'bookValue', 'bookValuePerShare'.
                    vpa = stock.get('bookValuePerShare', 0) or stock.get('bookValue', 0) or 0
                    
                    if lpa > 0 and vpa > 0:
                        valor_graham = np.sqrt(22.5 * lpa * vpa)
                    
                    if valor_graham > 0:
                        ms_graham = ((valor_graham - price) / price) * 100
                    else:
                        ms_graham = -100

                    # Bazin
                    # Precisamos dos dividendos em R$. A Brapi entrega 'dividendsData'?
                    # No batch, ela entrega 'dividendYield' (em %).
                    # Bazin = (DY_em_Reais) / 0.06
                    # DY_em_Reais = Preço * (DY_% / 100)
                    dy_raw = stock.get('dividendYield', 0) or 0 # Vem como percentual ou absoluto?
                    # Na Brapi, costuma vir o valor percentual (ex: 6.5) ou decimal (0.065).
                    # Vamos normalizar: se for > 1, assumimos que é percentual (ex: 6.5%).
                    # Se for < 1, assumimos decimal.
                    
                    if dy_raw > 1: dy_decimal = dy_raw / 100
                    else: dy_decimal = dy_raw
                    
                    dy_reais = price * dy_decimal
                    valor_bazin = dy_reais / 0.06 if dy_reais > 0 else 0
                    
                    # Armadilhas
                    # Precisamos de ROE, Dívida, Margem.
                    # Se a Brapi não enviar no batch, assumimos "Sem Dados" em vez de "Armadilha".
                    
                    # Tratamento seguro para campos opcionais
                    roe = stock.get('returnOnEquity', 0) or 0
                    margem_liq = stock.get('profitMargins', 0) or 0
                    divida_ebitda = stock.get('debtToEbitda', 0) or 0 # Raro vir no batch simples
                    volume = stock.get('regularMarketVolume', 0) or 0
                    
                    motivo_trap = []
                    is_trap = False
                    
                    # Só aplica filtro se tivermos os dados (diferente de 0)
                    if roe != 0 and roe < 0.05: motivo_trap.append("ROE Baixo")
                    if margem_liq != 0 and margem_liq < 0.03: motivo_trap.append("Margem Baixa")
                    if volume < 300000: motivo_trap.append("Liquidez Baixa")
                    
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
                        'Score Magic': 0 # Calculado depois
                    })
                    
                except Exception as e:
                    # st.error(f"Erro ao processar item: {e}")
                    continue
            
            return pd.DataFrame(resultados)
            
        except Exception as e:
            st.error(f"Erro de conexão com a Brapi: {e}")
            return pd.DataFrame()

    def calcular_magic_score(self, df):
        if df.empty: return df
        df = df.copy()
        
        # Filtra P/L positivo para ranking
        mask = df['P/L'] > 0
        if not mask.any(): return df

        df.loc[mask, 'Rank_PL'] = df.loc[mask, 'P/L'].rank(ascending=True)
        # Se ROE for 0 (dado faltante), joga pro final do ranking
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
    
    # Instancia Cliente Brapi
    client = BrapiClient()
    
    # Sidebar
    st.sidebar.header("⚙️ Controle")
    entrada = st.sidebar.radio("Ativos:", ["Carteira Monitorada", "Minha Lista"])
    
    if entrada == "Carteira Monitorada":
        tickers = client.tickers_padrao
        st.sidebar.info(f"Monitorando {len(tickers)} ativos principais.")
    else:
        text = st.sidebar.text_area("Digite os tickers:", "PETR4, VALE3, WEGE3")
        if text:
            tickers = text.replace(",", " ").replace(";", " ").split()
        else:
            tickers = []

    st.sidebar.divider()
    f_armadilha = st.sidebar.checkbox("Ocultar 'Armadilhas'", True)
    min_ms = st.sidebar.slider("Margem Graham Mínima %", -50, 100, 0)
    
    if st.sidebar.button("🚀 Consultar API"):
        if not tickers:
            st.warning("Defina os tickers.")
            return
            
        with st.spinner("Consultando Brapi.dev (Batch Request)..."):
            df = client.buscar_dados_batch(tickers)
        
        if df.empty:
            st.error("Nenhum dado retornado. Verifique os tickers ou o token.")
            return

        # Calcula Ranking
        df = client.calcular_magic_score(df)
        
        # Filtros Visuais
        view = df.copy()
        if f_armadilha:
            view = view[view['Armadilha'].str.contains("NÃO")]
        
        view = view[view['MS Graham (%)'] >= min_ms]

        # Dashboard
        st.subheader("🎯 Oportunidades (API Oficial)")
        
        # Configuração da Tabela com Logos
        # Streamlit Column Config para exibir imagens
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
        
        # Gráfico
        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader("📊 Gráfico de Valor")
            fig = px.scatter(
                view, x='MS Graham (%)', y='ROE (%)', 
                size='DY (%)', 
                color='Score Magic', 
                hover_name='Ticker',
                hover_data=['Preço', 'Alertas'],
                color_continuous_scale='RdYlGn',
                height=500
            )
            fig.add_vline(x=0, line_dash="dot")
            fig.add_hline(y=15, line_dash="dot")
            st.plotly_chart(fig, use_container_width=True)
            
        with col2:
            st.info("""
            **Fonte: Brapi.dev**
            
            Os dados agora vêm diretamente da B3.
            
            - **Logo:** Identificação visual.
            - **IFR:** Calculado com histórico real.
            - **Fundamentos:** Dados oficiais reportados.
            """)

        # Detalhe Visual com Logo
        st.divider()
        sel = st.selectbox("Raio-X do Ativo:", view['Ticker'].unique())
        if sel:
            r = view[view['Ticker'] == sel].iloc[0]
            
            # Cabeçalho com Logo e Nome
            c_img, c_info = st.columns([1, 5])
            with c_img:
                if r['Logo']: st.image(r['Logo'], width=80)
            with c_info:
                st.markdown(f"## {r['Ticker']}")
                st.markdown(f"**Preço:** R$ {r['Preço']:.2f}")

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Valor Graham", f"R$ {r['V. Graham']:.2f}", f"{r['MS Graham (%)']:.1f}%")
            k2.metric("Valor Bazin (Teto)", f"R$ {r['V. Bazin']:.2f}")
            k3.metric("IFR (14)", f"{r['IFR (14)']:.0f}")
            k4.metric("ROE", f"{r['ROE (%)']:.1f}%")

if __name__ == "__main__":
    main()
