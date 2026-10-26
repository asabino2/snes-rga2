# Retrogamers Aventura 2 (RGA2) — Edição 16-Bit (Super Nintendo / SNES)

Conversão completa em estilo **16-Bit Demake (SNES)** do jogo OpenBOR **Retrogamers Aventura 2**, desenvolvida em Assembly **65C816** nativo + driver de áudio **Sony SPC700 / S-DSP BRR** com gráficos, paletas (`BGR555`), retratos, fases e efeitos sonoros extraídos e convertidos diretamente dos arquivos originais do projeto OpenBOR.

---

## Arquivos Gerados (Prontos para Uso)

Todos os arquivos compilados estão na subpasta [`rom/`](./rom/):

1. **[`rom/RGA2_SNES.smc`](./rom/RGA2_SNES.smc)** *(4 MB / 32 Mbit — FastROM HiROM Mode `$31`, Headerless)*:
   - **Recomendado para Emuladores** (Snes9x, Mesen-S, bsnes, ZSNES, RetroArch, higan), **Super EverDrive / FXPAK Pro / SD2SNES** e gravação direta em uma única **EPROM 27C322 (32 Mbit)**.
   - Inclui cópia idêntica com extensão [`.sfc`](./rom/RGA2_SNES.sfc).
2. **[`rom/RGA2_SNES_ExHiROM_48Mbit.smc`](./rom/RGA2_SNES_ExHiROM_48Mbit.smc)** *(6 MB / 48 Mbit — FastROM ExHiROM Mode `$35`, Headerless)*:
   - Edição estendida **ExHiROM de 48 Mbit (6 MB)** com cabeçalhos duplos oficiais (`$00FFB0` e `$40FFB0`) e checksum espelhado padrão Nintendo (`Checksum: $846A`, `Complement: $7B95`, `XOR = $FFFF`), compatível com **SD2SNES / FXPAK Pro**, emuladores de precisão e placas repro ExHiROM multi-EPROM.
3. **Arquivos Binários para Gravadora de EPROM ([`rom/eprom/`](./rom/eprom/))**:
   - [`RGA2_EPROM_27C322_32Mbit.bin`](./rom/eprom/RGA2_EPROM_27C322_32Mbit.bin): Imagem de **4 MB (32 Mbit)** pronta para gravação direta em uma única **EPROM 27C322** (sem header de copiador de 512 bytes, alinhamento exato de hardware).
   - [`RGA2_ExHiROM_U1_27C322_32Mbit.bin`](./rom/eprom/RGA2_ExHiROM_U1_27C322_32Mbit.bin): Chip **U1 (Primeiros 32 Mbit / 4 MB — Banks `$C0-$FF`)** para placa ExHiROM de 48 Mbit.
   - [`RGA2_ExHiROM_U2_27C160_16Mbit.bin`](./rom/eprom/RGA2_ExHiROM_U2_27C160_16Mbit.bin): Chip **U2 (16 Mbit / 2 MB superiores — Banks `$40-$5F`)** para placa ExHiROM de 48 Mbit (usando decodificador `74LS139` no pino `A22 / /CART`).

---

## Conteúdo do Jogo Convertido para o SNES

### 6 Personagens Jogáveis (Retrogamers)
Cada personagem possui spritesheet `4bpp` próprio, retrato na tela de seleção e golpe especial exclusivo:
1. **Velberan** — *Equilibrado* (`Especial: Fantasma Comilão`)
2. **Sr. Wilson (Colônia Contra-Ataca)** — *Veloz* (`Especial: Freak Sonic Dash`)
3. **Pai Troll** — *Mestre de Combos* (`Especial: Pai Hyper Troll`)
4. **Snestalgia** — *Herói 16-Bit* (`Especial: Super Bazuca 16-Bit`)
5. **Baú do Old Gamer** — *Tanque Forte* (`Especial: Calendário Mortal`)
6. **Monique** — *Ágil & Técnica* (`Especial: Disparo Venenoso`)

### Hub Interativo + Fase BGS + 8 Mundos/Portais + Chefes
- **Fase 0 — Brasil Game Show (`BGS`)**: Enfrente os capangas no evento e derrote o **BGS Boss** para liberar o fliperama misterioso.
- **Estação Central (`HUB`)**: Caminhe livremente pela estação e entre em qualquer um dos **8 Portais** na ordem que desejar (o progresso de portais vencidos é salvo automaticamente na **Battery SRAM** do cartucho/EverDrive!):
  1. **Portal 1 — Mega Man X**: Inimigos `Megathug` | Chefe: **NutellaMan**
  2. **Portal 2 — Turtles (TMNT)**: Inimigos `Foot Ninja` | Chefe: **Batman**
  3. **Portal 3 — Golden Axe**: Inimigos `Grunt` | Chefe: **Gigante**
  4. **Portal 4 — Street Fighter**: Inimigos `Ryu` | Chefe: **Trank (Akuma)**
  5. **Portal 5 — Ninja Gaiden 8-Bit**: Inimigos `NinjaG` | Chefe: **ZangFake 8B**
  6. **Portal 6 — Super Mario World**: Inimigos `Goomba` | Chefe: **Koopa**
  7. **Portal 7 — Battletoads**: Inimigos `8-Bit Pig` | Chefe: **RatoBig**
  8. **Portal 8 — YouTube HQ (Final)**: Inimigos `Memeguy` | Chefe Final: **Ei Spoiled (O Algoritmo)**

---

## Controles no Super Nintendo

| Botão do SNES | Ação no Jogo |
| :--- | :--- |
| **Direcional (D-Pad)** | Movimentação em 8 direções (`X` e profundidade `Z`) / Troca personagem |
| **Botão Y** | Ataque / Combo de 3 Golpes (`Jab -> Cross -> Finalizador`) / Voadora no ar |
| **Botão B** | Pulo (combine com `Y` no ar para Voadora) |
| **Botão X ou A** | **Ataque Especial** (consome 20 MP, dispara projétil perfurante + onda de choque; pode cancelar combos normais) |
| **Botões L ou R** | Defesa / Bloqueio (`Block` — reduz o dano recebido para apenas 1 HP) |
| **CIMA (UP) ou Y** | Entrar em um Portal na Estação Central (`HUB`) |
| **START** | Confirmar nos menus / Iniciar jogo |
| **SELECT** *(na seleção)* | Atalho direto para a **Estação Central (Hub)** com todos os 8 portais |

---

## Estrutura do Código-Fonte (`snes_rga2/`)

- [`src/hardware.inc`](./src/hardware.inc) — Mapeamento de registradores PPU (`$2100-$213F`), APU (`$2140-$2143`), CPU/DMA (`$4200-$437F`), Direct Page (`$00-$7F`), WRAM e Battery SRAM (`$B0:6000`).
- [`src/init_boot.asm`](./src/init_boot.asm) — Vetor de Reset 65C816 (`SEI; CLC; XCE`), ativação de FastROM (`3.58 MHz`), limpeza de WRAM/VRAM/CGRAM/OAM, protocolo de upload **Sony SPC700 IPL Boot ROM** com proteção de timeout para console real/EverDrive, e inicialização de SRAM.
- [`src/dma_ppu.asm`](./src/dma_ppu.asm) — Rotina de interrupção VBlank (`NMIHandler`), DMA de OAM e BG3 HUD, scroll parallax (`BG2 = BG1 >> 1`), e carregamento de bancos gráficos de fases e sprites.
- [`src/hud_text.asm`](./src/hud_text.asm) — Renderizador de HUD Arcade em `BG3 2bpp` com alta prioridade (barras de HP, MP, barra de vida do Chefe, vidas, pontuação e textos em português).
- [`src/gameplay.asm`](./src/gameplay.asm) — Máquina de estados, Tela de Título, Intro, Seleção dos 6 Retrogamers, Estação Central (`Hub`) e motor Beat 'em Up 2.5D completo.
- [`src/data_tables.asm`](./src/data_tables.asm) — Tabelas de atributos dos 6 personagens, bancos de fases, coordenadas dos 8 portais e textos.
- [`tools/gif_snes_converter.py`](./tools/gif_snes_converter.py) — Conversor gráfico de `.gif` do OpenBOR para tiles planares `4bpp`/`2bpp`, tilemaps e paletas `BGR555` do SNES.
- [`tools/wav_to_brr.py`](./tools/wav_to_brr.py) — Conversor de efeitos `.wav` do OpenBOR para blocos **S-DSP BRR** + sintetizador de instrumentos e montador do driver **SPC700** com 12 músicas chiptune.
- [`tools/asm65816.py`](./tools/asm65816.py) & [`tools/build_snes_rom.py`](./tools/build_snes_rom.py) — Montador cruzado 65C816 de dois passos e linker de bancos HiROM/ExHiROM com cálculo de checksum oficial.
- [`tools/verify_rom.py`](./tools/verify_rom.py) — Suíte automatizada de verificação e simulação de hardware 65C816 + PPU + DMA + SPC700.

Para recompilar todo o projeto a partir dos arquivos originais do OpenBOR, basta executar:
```bat
snes_rga2\build_all.bat
```
