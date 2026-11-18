# Worldgen Engine

Gerador procedural de mundos com simulação básica de entidades e evolução do terreno.

O projeto combina relevo de origem tectônica, clima, hidrologia, biomas e recursos em um mundo organizado por células. É possível explorar suas camadas no terminal, exportar imagens e salvar o estado completo para continuar a simulação depois.

**Status:** protótipo em desenvolvimento. Os processos ambientais utilizam modelos simplificados e unidades de referência próprias.

## Funcionalidades

- **Geração por seed:** reprodução do estado inicial usando a mesma configuração e versão do código.
- **Relevo procedural:** placas tectônicas, fronteiras convergentes e divergentes e ruído em múltiplas escalas.
- **Clima:** índice de temperatura, transporte de umidade e precipitação influenciada pelo relevo.
- **Hidrologia:** oceanos, drenagem, acumulação de escoamento, lagos e rios.
- **Ecologia:** classificação de biomas, distribuição de árvores e cactos e depósitos de alimento, madeira e minério.
- **Entidades:** posição, saúde, fome, sede e busca de caminhos até água e alimento.
- **Evolução geológica:** soerguimento, subsidência, erosão, transporte e deposição de sedimentos.
- **Persistência:** salvamento em JSON, incluindo entidades, terreno, relógios e estado dos geradores pseudoaleatórios.
- **Visualização:** mapas no terminal e exportação de cinco camadas em PNG.

## Instalação

Requer Python 3.10 ou superior e `pip`. O ambiente utilizado no desenvolvimento é Python 3.15.

Após baixar o projeto, abra um terminal na pasta raiz e crie um ambiente virtual.

### Windows — PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

### Linux e macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

## Uso interativo

```bash
python main.py
```

O programa apresenta o menu abaixo:

```text
1 Gerar mundo | 2 Resumo | 3 Mapa | 4 Umidade | 5 Exportar imagens
6 Adicionar entidades | 7 Simular ticks | 8 Evoluir terreno | 9 Salvar | 10 Carregar | 0 Sair
```

Um fluxo inicial de exploração:

1. Escolha **1** e informe largura, altura e uma seed opcional. Comece com um mapa de `150 × 150` células para experimentar.
2. Use **3**, **4** ou **5** para visualizar o terreno e suas camadas.
3. Escolha **6** para adicionar entidades em posições terrestres.
4. Use **7** para avançar a simulação das entidades.
5. Use **8** para aplicar um passo de evolução geológica.
6. Escolha **9** para salvar o mundo antes de sair.

O programa só avança quando você solicita uma ação. **Sair não salva automaticamente.** Gerar ou carregar outro mundo substitui o mundo atual em memória.

## Uso pela linha de comando

### Gerar um mundo e exportar imagens

```bash
python main.py --generate --width 50 --height 40 --seed 435635 --export
```

### Adicionar entidades, simular e salvar

```bash
python main.py --generate --width 50 --height 40 --seed 435635 --entities 10 --ticks 100 --save data/worlds/mundo.json
```

### Continuar um mundo salvo

```bash
python main.py --load data/worlds/mundo.json --ticks 50 --save data/worlds/mundo.json
```

### Evoluir o terreno e exportar o resultado

```bash
python main.py --load data/worlds/mundo.json --years 100 --save data/worlds/mundo.json --export --output-dir data/img/evolucao
```

### Opções disponíveis

| Argumento | Finalidade | Padrão |
| --- | --- | --- |
| `--generate` | Gerar um mundo sem abrir o menu | Desativado |
| `--width` | Largura em células | `150` |
| `--height` | Altura em células | `150` |
| `--seed` | Seed inteira para geração | Aleatória |
| `--entities` | Quantidade de entidades a adicionar | `0` |
| `--ticks` | Passos da simulação das entidades | `0` |
| `--years` | Duração de um passo de evolução geológica | `0` |
| `--load` | Arquivo JSON a carregar | — |
| `--save` | Arquivo JSON de destino | — |
| `--export` | Exportar as cinco imagens | Desativado |
| `--output-dir` | Pasta de destino das imagens | `data/img/` |

Use `python main.py --help` para consultar a ajuda.

Para executar ações por argumentos, escolha `--generate` ou `--load`. As opções são aplicadas nesta ordem: gerar/carregar → adicionar entidades → evoluir terreno → simular ticks → salvar → exportar. Ao carregar um mundo, `--entities` adiciona novas entidades às existentes.

## Como o mundo é construído

```text
Configuração e seed
        ↓
Placas tectônicas e fronteiras
        ↓
Elevação regional + relevo tectônico + ruído
        ↓
Oceano e precipitação
        ↓
Drenagem, escoamento, lagos e rios
        ↓
Distância da água, umidade e diferenças de altura
        ↓
Biomas, vegetação e recursos
        ↓
Mundo disponível para exploração e simulação
```

As coordenadas usam `(x, y)`, com origem no canto superior esquerdo. As matrizes são acessadas por `[y][x]`. A borda esquerda se conecta à direita; as bordas norte e sul permanecem limitadas.

Existem dois relógios independentes:

- **Ticks:** atualizam necessidades, movimento, consumo e renovação de recursos.
- **Anos geológicos:** aplicam alterações de altura e erosão, recalculando as camadas ambientais afetadas.

Avançar um desses relógios não avança o outro.

## Imagens exportadas

| Camada | Conteúdo |
| --- | --- |
| `biomes` | Biomas com marcadores de árvores e cactos |
| `moisture` | Umidade, com água em azul |
| `temperature` | Índice térmico: azul para frio, branco intermediário e vermelho para quente |
| `elevation` | Elevação em tons de cinza, com escala de exibição fixa de `0` a `1` |
| `convergence` | Elevação com fronteiras tectônicas convergentes em vermelho |

Por padrão, cada célula ocupa `4 × 4` pixels. Os nomes dos arquivos incluem data, horário, dimensões, seed e camada. A exportação utiliza o estado atual, sem gerar outro mundo.

## Configuração

Os parâmetros ambientais e de simulação estão em [`app/config.py`](app/config.py), na classe `WorldConfig`. Para uma configuração personalizada, também é possível utilizar o projeto diretamente em Python:

```python
from app.config import WorldConfig
from app.persistence import save_world
from app.world import World

world = World(
    WorldConfig(
        width=50,
        height=40,
        seed=435635,
        sea_level=0.35,
        num_plates=8,
        resource_regrowth_ticks=25,
    ),
    name="Mundo de exemplo",
)

world.populate(10)
world.advance(50)
budget = world.evolve_terrain(years=10)
save_world(world, "data/worlds/exemplo.json")
```

O arquivo `.env` na raiz permite configurar os logs:

```dotenv
LOG_LEVEL=DEBUG
LOG_DIR=data/logs
LOG_FILE=app.log
LOG_CONSOLE=false
```

O arquivo é opcional; existem valores padrão. `LOG_CONSOLE=true` habilita mensagens de log no terminal. As pastas de saída são criadas conforme necessário.

## Estrutura do projeto

```text
worldgen-engine/
├── main.py                 # Entrada da aplicação
├── requirements.txt        # Dependências externas
├── app/
│   ├── cli.py              # Menu e argumentos de terminal
│   ├── config.py           # Parâmetros e validação
│   ├── world.py            # Estado central e ciclo de vida do mundo
│   ├── map.py              # Terreno e coordenação da geração
│   ├── tectonics.py        # Placas, fronteiras e campos tectônicos
│   ├── climate.py          # Temperatura, precipitação e umidade
│   ├── hydrology.py        # Oceanos, drenagem, lagos e rios
│   ├── ecology.py          # Relevo, biomas, vegetação e recursos
│   ├── geology.py          # Solo, rocha e erosão
│   ├── entity.py           # Estado das entidades
│   ├── simulation.py       # Comportamento e renovação de recursos
│   ├── persistence.py      # Salvamento e carregamento JSON
│   ├── terminal.py         # Visualizações no terminal
│   ├── palette.py          # Cores RGB
│   ├── save_img.py         # Exportação de biomas e umidade
│   ├── diagnostics.py      # Exportação de diagnósticos
│   ├── png.py              # Escrita compartilhada de PNG
│   └── logger.py           # Configuração de logs
├── tests/
│   └── test_engine.py      # Testes automatizados
└── data/                   # Imagens, logs e mundos salvos
```

## Testes

```bash
python -B -m unittest discover -s tests -v
```

A suíte verifica reprodução por seed, drenagem sem ciclos, conservação de escoamento e sedimentos, comportamento das entidades, renovação de recursos, retomada de snapshots e integridade dos arquivos PNG.

## Limitações atuais

- O terreno utiliza uma grade bidimensional de alturas, sem renderização 3D ou editor visual.
- As placas permanecem fixas; suas velocidades definem interações e taxas de alteração vertical.
- Temperatura, escoamento, erosão e sedimentos usam unidades de protótipo, sem calibração física.
- O clima representa um padrão estacionário; não há estações ou meteorologia dinâmica.
- Lagos usam uma hipótese simplificada de preenchimento; rios não possuem largura e profundidade simuladas.
- Entidades têm comportamento de sobrevivência básico, sem reprodução, combate, sociedades ou uso ativo do inventário. Os mapas ainda não exibem entidades.
- Vegetação é uma camada do terreno; sua renovação biológica não é simulada. Alimento e madeira são repostos nos depósitos iniciais.
- Um passo geológico longo pode produzir um resultado diferente de vários passos curtos, devido aos limites aplicados à erosão.
- Mapas grandes e populações numerosas podem aumentar significativamente o custo de geração e busca de caminhos.
- O formato JSON possui versão, mas ainda não há migração entre versões de snapshots.