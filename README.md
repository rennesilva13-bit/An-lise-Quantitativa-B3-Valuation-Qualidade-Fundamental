# 💎 B3 Pro Analyzer - Titanium Edition (DCF Master)

Análise quantitativa avançada de ações da B3 com valuation por **Fluxo de Caixa Descontado (DCF)** e métricas fundamentalistas.

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30%2B-red)
![License](https://img.shields.io/badge/License-MIT-green)

## 🚀 Funcionalidades

### 📊 Valuation Avançado
- **DCF de 2 Estágios:** Projeção de crescimento + perpetuidade
- **Matriz de Sensibilidade:** Análise de cenários (WACC vs Growth)
- **Valor de Graham:** Método clássico de Benjamin Graham
- **Margem de Segurança:** Cálculo automático para cada ativo

### 🎯 Análise Fundamental
- **Score de Qualidade (Magic Formula):** Ranking baseado em ROE, P/L e momentum
- **Detector de Armadilhas:** Identifica ações baratas mas problemáticas
- **Comparação Setorial:** Benchmarking por setor de atuação
- **Métricas Essenciais:** P/L, P/VP, ROE, Dividend Yield, Dívida/EBITDA

### 📈 Visualizações Interativas
- Ranking completo com filtros personalizáveis
- Heatmap de sensibilidade DCF
- Gráficos de dispersão (P/L vs ROE)
- Análise setorial com top performers

### ⚡ Performance
- Busca paralela de dados (ThreadPoolExecutor)
- Cache otimizado com session state
- Tratamento robusto de erros e timeouts
- Interface responsiva e intuitiva

## 📦 Instalação

### Pré-requisitos
- Python 3.8 ou superior
- pip (gerenciador de pacotes Python)

### Passo a Passo

1. **Clone o repositório**
```bash
git clone https://github.com/seu-usuario/b3-pro-analyzer.git
cd b3-pro-analyzer
```

2. **Crie um ambiente virtual (recomendado)**
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

3. **Instale as dependências**
```bash
pip install -r requirements.txt
```

4. **Execute a aplicação**
```bash
streamlit run app.py
```

5. **Acesse no navegador**
```
http://localhost:8501
```

## 🎓 Como Usar

### 1️⃣ Seleção de Ativos
Escolha entre:
- **Carteira Sugerida:** 35+ ações selecionadas com boa liquidez
- **Minha Lista:** Insira seus próprios tickers (ex: WEGE3, VALE3, PETR4)

### 2️⃣ Configuração de Premissas DCF
Ajuste os parâmetros globais:
- **WACC (8-20%):** Taxa de desconto / custo de capital
- **Crescimento (0-20%):** Taxa de crescimento esperada (5 anos)
- **Crescimento Perpétuo (0-6%):** Taxa de crescimento na perpetuidade

### 3️⃣ Análise dos Resultados

#### 🏆 Ranking Geral
- Visualize todas as ações ranqueadas por Score de Qualidade
- Compare Valor de Graham vs Valor DCF
- Identifique oportunidades com alta margem de segurança

#### 🏢 Análise Setorial
- Compare ativos do mesmo setor
- Visualize métricas medianas do setor
- Identifique o líder de cada segmento

#### 💎 DCF Detalhado
- Selecione um ativo específico
- Ajuste premissas personalizadas
- Analise matriz de sensibilidade
- Veja diferentes cenários de valuation

## 📊 Métricas Explicadas

| Métrica | Descrição | Valor Ideal |
|---------|-----------|-------------|
| **P/L** | Preço/Lucro - Quanto você paga por R$ 1 de lucro | 8-15x |
| **ROE** | Rentabilidade sobre patrimônio | > 15% |
| **P/VP** | Preço/Valor Patrimonial | < 2.0 |
| **DY** | Dividend Yield - Rendimento de dividendos | > 4% |
| **Dívida/EBITDA** | Alavancagem financeira | < 3.0 |
| **V. Graham** | Valor intrínseco (Graham) | > Preço Atual |
| **V. DCF** | Valor intrínseco (DCF) | > Preço Atual |
| **MS DCF** | Margem de Segurança DCF | > 20% |
| **Score Magic** | Qualidade fundamental (0-100) | > 70 |

## 🔬 Metodologia DCF

O modelo de **Fluxo de Caixa Descontado** utilizado segue 2 estágios:

### Estágio 1: Crescimento Explícito (5 anos)
```
FCF₁ = FCF₀ × (1 + g)¹
FCF₂ = FCF₀ × (1 + g)²
...
FCF₅ = FCF₀ × (1 + g)⁵
```

### Estágio 2: Perpetuidade
```
Valor Terminal = FCF₅ × (1 + g_perpetuo) / (WACC - g_perpetuo)
```

### Valor Presente
```
Valor Empresa = Σ(FCFₜ / (1 + WACC)ᵗ) + VT / (1 + WACC)⁵
Valor Patrimônio = Valor Empresa - Dívida Líquida
Preço Justo = Valor Patrimônio / Ações Outstanding
```

## 🛡️ Detector de Armadilhas

O sistema identifica automaticamente "Value Traps" (armadilhas de valor) - ações que parecem baratas mas têm problemas fundamentais:

**Flags de Alerta:**
- ⚠️ P/L < 5 (muito baixo pode indicar problemas)
- ⚠️ Dívida/EBITDA > 5 (alta alavancagem)
- ⚠️ Margem Líquida < 0 (prejuízo)
- ⚠️ ROE < 5% (baixa rentabilidade)

## 📁 Estrutura do Projeto

```
b3-pro-analyzer/
├── app.py                 # Aplicação principal Streamlit
├── requirements.txt       # Dependências Python
├── README.md             # Documentação
└── .gitignore            # Arquivos ignorados pelo Git
```

## 🔧 Tecnologias Utilizadas

- **Streamlit** - Interface web interativa
- **Pandas** - Manipulação de dados
- **NumPy** - Cálculos numéricos
- **Plotly** - Visualizações gráficas
- **Requests** - Consumo da API Brapi
- **ThreadPoolExecutor** - Processamento paralelo

## 📡 API Brapi.dev

Este projeto utiliza a [Brapi.dev](https://brapi.dev) para obter dados de mercado da B3.

**Dados disponíveis:**
- Cotações em tempo real
- Fundamentalistas (balanços, DRE)
- Histórico de preços
- Dividendos
- Indicadores financeiros

## ⚠️ Avisos Importantes

1. **Não é recomendação de investimento:** Esta ferramenta é apenas para fins educacionais e de análise. Sempre faça sua própria pesquisa.

2. **Dados podem ter atraso:** As informações vêm de APIs públicas e podem não estar 100% atualizadas.

3. **DCF é uma estimativa:** O valuation por DCF depende de premissas que podem ou não se concretizar.

4. **Diversifique:** Nunca tome decisões baseadas em uma única métrica ou ferramenta.

## 🤝 Contribuindo

Contribuições são bem-vindas! Sinta-se livre para:

1. Fazer um Fork do projeto
2. Criar uma Branch para sua feature (`git checkout -b feature/NovaFuncionalidade`)
3. Commit suas mudanças (`git commit -m 'Adiciona nova funcionalidade'`)
4. Push para a Branch (`git push origin feature/NovaFuncionalidade`)
5. Abrir um Pull Request

## 📝 Melhorias Futuras

- [ ] Backtesting de estratégias
- [ ] Análise técnica integrada
- [ ] Comparação com fundos de investimento
- [ ] Alertas por e-mail/Telegram
- [ ] Export de relatórios em PDF
- [ ] Integração com mais APIs (Yahoo Finance, Alpha Vantage)
- [ ] Machine Learning para previsão de preços
- [ ] Dashboard personalizado por usuário
Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.

