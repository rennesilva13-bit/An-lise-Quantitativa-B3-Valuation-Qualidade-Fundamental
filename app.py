"""
B3 Quant Analyzer Pro - Value Investing & Technicals
====================================================
Melhorias de Robustez:
1. Multithreading: Coleta de dados paralela (muito mais rápido).
2. Dados Técnicos: Cálculo de IFR (RSI) para timing.
3. Validação de Dados: Tratamento robusto para evitar zeros/nulos.

Autor: Analista Quantitativo
Data: 2026
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
import warnings
from concurrent.futures import ThreadPoolExecutor

# Ignorar avisos
warnings.filterwarnings('ignore')

# --- Configuração da Página ---
st.set_page_config(
    page_title="B3 Value Investing Pro",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS Otimizado ---
st.markdown("""
<style>
    .main-header { font-size: 2rem; font-weight: bold; color: #0066cc; text-align: center; margin-bottom: 1rem; }
    div[data-testid="stMetric"] {
        background-color: #f0f2f6 !important;
        border-radius: 10px; padding: 15px; border-left: 5px solid #0066cc;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    div[data-testid="stMetric"] label { color: #333 !important; font-weight: 600 !important; }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] { color: #000 !important; font-weight: bold !important; }
    div[data-testid="stMetricDelta"] { font-weight: bold !important; }
</style>
""", unsafe_allow_html=True)

class B3Fundamentalist:
    def __init__(self):
        self.tickers_padrao = [
            'BBAS3', 'ITUB4', 'BBDC4', 'SANB11', 'TAEE11', 'TRPL4', 'CPLE6', 'EGIE3',
            'VALE3', 'CSNA3', 'GGBR4', 'WEGE3', 'PSSA3', 'BBSE3', 'CXSE3', 'SAPR11',
            'CMIG4', 'KLBN11', 'SUZB3', 'PRIO3', 'PETR4', 'JBSS3', 'MRFG3', 'GOAU4'
        ]

    def _tratar_ticker(self, ticker):
        """Limpa e formata o ticker."""
        ticker = ticker.replace("'", "").replace('"', "").strip().upper()
        if not ticker.endswith('.SA'): return f"{ticker}.SA"
        return ticker

    def calcular_rsi(self, data, window=14):
        """Calcula o Índice de Força Relativa (IFR/RSI) para robustez técnica."""
        if len(data) < window: return 50 # Neutro se não houver dados suficientes
        
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]

    def _coletar_ativo_unico(self, ticker_raw):
        """
        Função isolada para coletar dados de UM ativo.
        Usada pelo ThreadPoolExecutor para rodar em paralelo.
        """
        ticker = self._tratar_ticker(ticker_raw)
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # --- Robustez de Preço ---
            # Tenta fast_info, se falhar, tenta history
            try:
                price = stock.fast_info.last_price
            except:
                hist_price = stock.history(period="1d")
                if not hist_price.empty:
                    price = hist_price['Close'].iloc[-1]
                else:
                    return None # Ativo sem dados de preço

            # --- Robustez Técnica (RSI) ---
            # Baixa histórico curto para calcular IFR
            hist_tecnico = stock.history(period="1mo")
            if not hist_tecnico.empty:
                rsi = self.calcular_rsi(hist_tecnico)
            else:
                rsi = 50 # Neutro
            
            # --- Coleta Segura de Fundamentos ---
            # Usa 'get' com valor default 0 para evitar quebras
            lpa = info.get('trailingEps', 0) or 0
            vpa = info.get('bookValue', 0) or 0
            roe = info.get('returnOnEquity', 0) or 0
            divida_ebitda = info.get('debtToEbitda', 0) or 0
            margem_liq = info.get('profitMargins', 0) or 0
            dy_rate = info.get('dividendRate', 0) or 0
            # Se dividendRate for 0, tenta calcular pelo yield * preço
            if dy_rate == 0:
                dy_rate = (info.get('dividendYield', 0) or 0) * price

            dy_percent = info.get('dividendYield', 0) or 0
            volume = info.get('averageVolume', 0) or 0
            pl = info.get('trailingPE', 0) or 0
            setor = info.get('sector', 'Outros')

            # --- Cálculos de Valuation ---
            # Graham: Raiz(22.5 * LPA * VPA)
            if lpa > 0 and vpa > 0:
                valor_graham = np.sqrt(22.5 * lpa * vpa)
            else:
                valor_graham = 0
            
            # Margem de Segurança Graham
            if valor_graham > 0:
                ms_graham = ((valor_graham - price) / price) * 100
            else:
                ms_graham = -100

            # Bazin: Dividendos / 6%
            valor_bazin = dy_rate / 0.06 if dy_rate > 0 else 0

            # --- Detecção de Armadilhas ---
            motivo_trap = []
            if roe < 0.05: motivo_trap.append("ROE Baixo")
            if divida_ebitda > 5: motivo_trap.append("Dívida Crítica") # Tolerância maior
            if margem_liq < 0.02: motivo_trap.append("Margem Baixa")
            if volume < 300000: motivo_trap.append("Liquidez Baixa")
            
            return {
                'Ticker': ticker.replace('.SA', ''),
                'Setor': setor,
                'Preço Atual': price,
                'Valor Graham': valor_graham,
                'Valor Bazin': valor_bazin,
                'MS Graham (%)': ms_graham,
                'DY (%)': dy_percent * 100,
                'P/L': pl,
                'ROE (%)': roe * 100,
                'IFR (14)': rsi,
                'Dívida/EBITDA': divida_ebitda,
                'Armadilha': "⚠️ SIM" if motivo_trap else "🛡️ NÃO",
                'Alertas': ", ".join(motivo_trap) if motivo_trap else "OK",
                'Score Magic': 0 # Calculado depois
            }

        except Exception as e:
            # Em produção, logar o erro: print(f"Erro {ticker}: {e}")
            return None

    @st.cache_data(ttl=1800) # Cache de 30 min
    def buscar_dados_paralelo(_self, tickers):
        """Coleta dados usando múltiplas threads para velocidade máxima."""
        dados_validos = []
        
        # Cria um pool de threads (geralmente 10x mais rápido que loop normal)
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Mapeia a função de coleta para cada ticker
            results = list(executor.map(_self._coletar_ativo_unico, tickers))
        
        # Filtra resultados vazios (erros)
        dados_validos = [r for r in results if r is not None]
        
        return pd.DataFrame(dados_validos)

    def calcular_magic_score(self, df):
        if df.empty: return df
        df = df.copy()
        mask = df['P/L'] > 0
        if not mask.any(): return df

        # Ranking P/L (Menor é melhor) e ROE (Maior é melhor)
        df.loc[mask, 'Rank_PL'] = df.loc[mask, 'P/L'].rank(ascending=True)
        df.loc[mask, 'Rank_ROE'] = df.loc[mask, 'ROE (%)'].rank(ascending=False)
        
        # IFR também entra no critério de desempate? Por enquanto não, apenas visual.
        
        df['Magic_Points'] = df['Rank_PL'] + df['Rank_ROE']
        min_p, max_p = df['Magic_Points'].min(), df['Magic_Points'].max()
        
        if max_p != min_p:
            df['Score Magic'] = 100 * (1 - (df['Magic_Points'] - min_p) / (max_p - min_p))
        else:
            df['Score Magic'] = 50
            
        return df.sort_values('Score Magic', ascending=False).fillna(0)

def main():
    st.markdown('<div class="main-header">💎 B3 Quant Analyzer Pro</div>', unsafe_allow_html=True)
    analyzer = B3Fundamentalist()
    
    # Sidebar
    st.sidebar.header("⚙️ Painel de Controle")
    entrada = st.sidebar.radio("Ativos:", ["Carteira Sugerida", "Minha Lista"])
    
    if entrada == "Carteira Sugerida":
        tickers = analyzer.tickers_padrao
        st.sidebar.info(f"{len(tickers)} ativos monitorados.")
    else:
        text = st.sidebar.text_area("Digite os tickers:", "PETR4, VALE3, WEGE3")
        if text:
            import re
            limpo = text.replace('"', '').replace("'", "")
            tickers = [t for t in re.split(r'[,\s;]+', limpo) if t]
        else:
            tickers = []

    st.sidebar.divider()
    # Filtros Dinâmicos
    f_armadilha = st.sidebar.checkbox("Ocultar 'Armadilhas'", True)
    f_setor = st.sidebar.text_input("Filtrar por Setor (opcional):", placeholder="Ex: Financial")
    min_ms = st.sidebar.slider("Margem Graham Mínima %", -50, 100, 0)
    
    if st.sidebar.button("🚀 Executar Varredura"):
        if not tickers:
            st.warning("Insira tickers.")
            return
            
        with st.spinner(f"Analisando {len(tickers)} ativos em paralelo..."):
            df = analyzer.buscar_dados_paralelo(tickers)
        
        if df.empty:
            st.error("Falha na coleta. Verifique conexão.")
            return

        df = analyzer.calcular_magic_score(df)
        
        # Filtros de Exibição
        view = df.copy()
        if f_armadilha: view = view[view['Armadilha'].str.contains("NÃO")]
        if f_setor: view = view[view['Setor'].str.contains(f_setor, case=False, na=False)]
        view = view[view['MS Graham (%)'] >= min_ms]

        # Dashboard Top
        st.subheader("🎯 Melhores Oportunidades (Magic Formula)")
        cols = ['Ticker', 'Setor', 'Preço Atual', 'Valor Graham', 'MS Graham (%)', 'DY (%)', 'IFR (14)', 'Score Magic', 'Alertas']
        
        st.dataframe(
            view[cols].style.format({
                'Preço Atual': 'R$ {:.2f}', 'Valor Graham': 'R$ {:.2f}',
                'MS Graham (%)': '{:.1f}%', 'DY (%)': '{:.1f}%', 'IFR (14)': '{:.0f}', 'Score Magic': '{:.0f}'
            }).background_gradient(cmap='Greens', subset=['MS Graham (%)', 'Score Magic']),
            use_container_width=True, height=400
        )

        # Gráfico Cruzado
        st.divider()
        c1, c2 = st.columns([3, 1])
        with c1:
            st.subheader("📊 Fundamental (X) vs Técnico (Tamanho)")
            fig = px.scatter(
                view, x='MS Graham (%)', y='ROE (%)', 
                size='IFR (14)', # Tamanho da bolinha agora é o IFR
                color='Score Magic', hover_name='Ticker', hover_data=['Setor', 'Preço Atual'],
                labels={'MS Graham (%)': 'Desconto Graham', 'ROE (%)': 'Qualidade ROE'},
                color_continuous_scale='RdYlGn', height=500
            )
            fig.add_vline(x=0, line_dash="dot", opacity=0.5)
            fig.add_hline(y=15, line_dash="dot", opacity=0.5)
            st.plotly_chart(fig, use_container_width=True)
        
        with c2:
            st.info("""
            **Legenda Visual:**
            
            🟢 **Cor:** Score Magic (Qualidade + Preço).
            
            🔵 **Tamanho:** IFR (RSI).
            * Bolinha pequena: IFR baixo (Pode estar sobrevendido/barato).
            * Bolinha grande: IFR alto (Pode estar "esticado").
            """)

        # Detalhes
        st.divider()
        sel = st.selectbox("Examinar Ativo:", view['Ticker'].unique())
        if sel:
            r = view[view['Ticker'] == sel].iloc[0]
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Preço", f"R$ {r['Preço Atual']:.2f}")
            k2.metric("Valor Graham", f"R$ {r['Valor Graham']:.2f}", f"{r['MS Graham (%)']:.1f}%")
            
            ifr_val = r['IFR (14)']
            k3.metric("IFR (14)", f"{ifr_val:.0f}", "Sobrecomprado" if ifr_val > 70 else "Sobrevendido" if ifr_val < 30 else "Neutro", delta_color="inverse")
            
            k4.metric("ROE", f"{r['ROE (%)']:.1f}%")
            
            if r['Alertas'] != "OK": st.error(f"⚠️ {r['Alertas']}")
            else: st.success("✅ Aprovado nos filtros de segurança.")

if __name__ == "__main__":
    main()
