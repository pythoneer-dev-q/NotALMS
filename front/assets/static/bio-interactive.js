/**
 * NotALMS BioInteractive Widgets
 * Interactive biological learning widgets:
 * 1. Genetic Table Reference Modal
 * 2. Nucleotide Builder (Drag-and-Drop / Click-to-assemble)
 * 3. Polynucleotide Chain Assembly (5' -> 3' complementary builder)
 * 4. tRNA Secondary Structure ("Cloverleaf" / Трилистник) Folding Widget
 */

(function () {
  'use strict';

  // Внедрение стилей интерактива
  function ensureStyles() {
    if (document.getElementById('bio-interactive-styles')) return;
    const style = document.createElement('style');
    style.id = 'bio-interactive-styles';
    style.textContent = `
      *, *::before, *::after {
        -webkit-tap-highlight-color: transparent !important;
      }
      .bio-widget-wrap {
        background: var(--surface2, #131a2a);
        border: 1px solid var(--line2, rgba(255,255,255,0.12));
        border-radius: 16px;
        padding: 18px;
        margin: 14px 0;
        display: flex;
        flex-direction: column;
        gap: 16px;
        color: var(--text, #edf2ff);
        font-family: 'Onest', sans-serif;
        box-shadow: 0 8px 24px -10px rgba(0,0,0,0.5);
      }
      .bio-widget-title {
        font-size: 1.05rem;
        font-weight: 700;
        display: flex;
        align-items: center;
        gap: 8px;
        color: var(--primary, #6366f1);
      }
      .bio-widget-desc {
        font-size: 0.9rem;
        color: var(--muted, #9daac4);
        line-height: 1.45;
      }
      .bio-palette {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        padding: 12px;
        background: rgba(0,0,0,0.22);
        border-radius: 12px;
        border: 1px dashed var(--line2, rgba(255,255,255,0.15));
      }
      .bio-palette-label {
        width: 100%;
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--muted, #9daac4);
        margin-bottom: 2px;
      }
      .bio-chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 8px 14px;
        border-radius: 10px;
        background: var(--surface, #1e293b);
        border: 1px solid var(--line2, rgba(255,255,255,0.14));
        color: var(--text, #fff);
        font-weight: 600;
        font-size: 0.92rem;
        cursor: grab;
        user-select: none;
        transition: all 0.16s ease;
        -webkit-tap-highlight-color: transparent !important;
      }
      .bio-chip:hover {
        border-color: var(--primary, #6366f1);
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(99,102,241,0.25);
      }
      .bio-chip.active-selected {
        border-color: var(--accent, #4ade80);
        background: color-mix(in srgb, var(--accent, #4ade80) 20%, var(--surface, #1e293b));
        box-shadow: 0 0 0 2px var(--accent, #4ade80);
      }
      .bio-chip-nuc { min-width: 44px; justify-content: center; font-family: monospace; font-size: 1.15rem; }
      .bio-chip-sugar { background: color-mix(in srgb, #f59e0b 14%, var(--surface, #1e293b)); border-color: rgba(245,158,11,0.3); }
      .bio-chip-base { background: color-mix(in srgb, #6366f1 14%, var(--surface, #1e293b)); border-color: rgba(99,102,241,0.3); }
      .bio-chip-phos { background: color-mix(in srgb, #ef4444 14%, var(--surface, #1e293b)); border-color: rgba(239,68,68,0.3); }

      /* Nucleotide Assembly Dock */
      .bio-dock {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 12px;
        align-items: stretch;
      }
      @media(max-width: 640px) {
        .bio-dock { grid-template-columns: 1fr; }
      }
      .bio-dock-slot {
        background: rgba(0,0,0,0.3);
        border: 2px dashed var(--line2, rgba(255,255,255,0.18));
        border-radius: 12px;
        padding: 14px;
        min-height: 100px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 6px;
        text-align: center;
        transition: all 0.2s;
        cursor: pointer;
        position: relative;
        -webkit-tap-highlight-color: transparent !important;
      }
      .bio-dock-slot.drag-over {
        border-color: var(--accent, #4ade80);
        background: color-mix(in srgb, var(--accent, #4ade80) 12%, rgba(0,0,0,0.3));
      }
      .bio-dock-slot.filled {
        border-style: solid;
        border-color: var(--primary, #6366f1);
        background: color-mix(in srgb, var(--primary, #6366f1) 10%, rgba(0,0,0,0.3));
      }
      .bio-slot-title { font-size: 0.78rem; text-transform: uppercase; color: var(--muted, #9daac4); font-weight: 600; }
      .bio-slot-val { font-size: 1.1rem; font-weight: 700; color: var(--text, #fff); }

      /* Polynucleotide Chain Assembly */
      .bio-chain-row {
        display: flex;
        align-items: center;
        gap: 8px;
        overflow-x: auto;
        padding: 12px 6px;
      }
      .bio-chain-end {
        font-weight: 800;
        font-family: monospace;
        font-size: 1.15rem;
        color: var(--primary, #6366f1);
        padding: 4px 8px;
        background: rgba(99,102,241,0.12);
        border-radius: 8px;
      }
      .bio-chain-slot {
        width: 52px;
        height: 64px;
        border: 2px dashed var(--line2, rgba(255,255,255,0.2));
        border-radius: 10px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        font-family: monospace;
        font-size: 1.3rem;
        font-weight: 800;
        background: rgba(0,0,0,0.25);
        cursor: pointer;
        position: relative;
        flex-shrink: 0;
        transition: all 0.18s;
        -webkit-tap-highlight-color: transparent !important;
      }
      .bio-chain-slot.filled {
        border-style: solid;
        border-color: var(--accent, #4ade80);
        background: color-mix(in srgb, var(--accent, #4ade80) 15%, rgba(0,0,0,0.3));
        color: var(--accent, #4ade80);
      }
      .bio-chain-slot .slot-idx {
        position: absolute;
        bottom: 2px;
        font-size: 0.62rem;
        color: var(--muted, #9daac4);
      }
      .bio-bonds-indicator {
        font-size: 0.72rem;
        color: var(--muted, #9daac4);
        display: flex;
        align-items: center;
        gap: 12px;
        margin-top: 4px;
      }

      /* tRNA Cloverleaf Folding */
      .bio-cloverleaf-box {
        display: grid;
        grid-template-columns: 1fr;
        gap: 14px;
      }
      .bio-clover-diagram {
        width: 100%;
        max-width: 440px;
        margin: 0 auto;
        background: rgba(0,0,0,0.3);
        border: 1px solid var(--line2, rgba(255,255,255,0.12));
        border-radius: 16px;
        padding: 16px;
        display: flex;
        flex-direction: column;
        align-items: center;
        position: relative;
      }
      .bio-clover-fold-btn {
        background: var(--primary, #6366f1);
        color: #fff;
        border: 0;
        padding: 10px 18px;
        border-radius: 10px;
        font-weight: 700;
        cursor: pointer;
        transition: all 0.2s;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        -webkit-tap-highlight-color: transparent !important;
      }
      .bio-clover-fold-btn:hover {
        filter: brightness(1.1);
        transform: translateY(-1px);
      }
      .bio-anticodon-inputs {
        display: flex;
        gap: 8px;
        align-items: center;
        justify-content: center;
      }
      .bio-anticodon-triplet-input {
        width: 44px;
        height: 48px;
        text-align: center;
        font-size: 1.3rem;
        font-weight: 800;
        font-family: monospace;
        background: var(--surface, #1e293b);
        border: 2px solid var(--primary, #6366f1);
        border-radius: 10px;
        color: var(--text, #fff);
        text-transform: uppercase;
        -webkit-tap-highlight-color: transparent !important;
      }

      /* Genetic Table Modal */
      .gen-modal-overlay {
        position: fixed;
        inset: 0;
        background: rgba(3, 7, 18, 0.78);
        backdrop-filter: blur(6px);
        z-index: 9999;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 14px;
        -webkit-tap-highlight-color: transparent !important;
      }
      .gen-modal-card {
        background: var(--panel, #111a2e);
        border: 1px solid var(--line2, rgba(255,255,255,0.18));
        border-radius: 16px;
        max-width: 820px;
        width: 100%;
        max-height: 92vh;
        overflow-y: auto;
        padding: 22px;
        box-shadow: 0 24px 60px rgba(0,0,0,0.8);
      }
      .gen-modal-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 14px;
        padding-bottom: 12px;
        border-bottom: 1px solid var(--line, rgba(255,255,255,0.08));
      }
      .gen-modal-title { font-size: 1.15rem; font-weight: 700; color: var(--text, #fff); display: flex; align-items: center; gap: 8px; }
      .gen-search-bar { margin-bottom: 12px; }
      .gen-search-input {
        width: 100%;
        background: var(--surface2, #182236);
        border: 1px solid var(--line2, rgba(255,255,255,0.14));
        color: var(--text, #fff);
        border-radius: 10px;
        padding: 9px 14px;
        font-family: inherit;
        font-size: 0.92rem;
      }
      .gen-table-wrap { overflow-x: auto; }
      .gen-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.85rem;
        text-align: center;
      }
      .gen-table th, .gen-table td {
        border: 1px solid var(--line2, rgba(255,255,255,0.1));
        padding: 6px 8px;
      }
      .gen-table th { background: rgba(99,102,241,0.12); color: var(--primary, #6366f1); font-weight: 700; }
      .gen-table td.codon-cell { cursor: pointer; transition: background 0.15s; font-family: monospace; }
      .gen-table td.codon-cell:hover { background: rgba(99,102,241,0.25); color: #fff; }
      .gen-table td.highlight { background: color-mix(in srgb, var(--accent, #4ade80) 30%, transparent)!important; color: #fff!important; font-weight: 800; }
      .gen-table-btn {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: transparent;
        border: 1px solid var(--primary, #6366f1);
        color: var(--primary, #6366f1);
        padding: 6px 12px;
        border-radius: 8px;
        font-size: 0.84rem;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.16s;
        -webkit-tap-highlight-color: transparent !important;
      }
      .gen-table-btn:hover {
        background: rgba(99,102,241,0.15);
      }
    `;
    document.head.appendChild(style);
  }

  // 1. Таблица генетического кода
  const GENETIC_MAP = {
    'УУУ': 'ФЕН', 'УУЦ': 'ФЕН', 'УУА': 'ЛЕЙ', 'УУГ': 'ЛЕЙ',
    'ЦУУ': 'ЛЕЙ', 'ЦУЦ': 'ЛЕЙ', 'ЦУА': 'ЛЕЙ', 'ЦУГ': 'ЛЕЙ',
    'АУУ': 'ИЛЕ', 'АУЦ': 'ИЛЕ', 'АУА': 'ИЛЕ', 'АУГ': 'МЕТ',
    'ГУУ': 'ВАЛ', 'ГУЦ': 'ВАЛ', 'ГУА': 'ВАЛ', 'ГУГ': 'ВАЛ',
    'УЦУ': 'СЕР', 'УЦЦ': 'СЕР', 'УЦА': 'СЕР', 'УЦГ': 'СЕР',
    'ЦЦУ': 'ПРО', 'ЦЦЦ': 'ПРО', 'ЦЦА': 'ПРО', 'ЦЦГ': 'ПРО',
    'АЦУ': 'ТРЕ', 'АЦЦ': 'ТРЕ', 'АЦА': 'ТРЕ', 'АЦГ': 'ТРЕ',
    'ГЦУ': 'АЛА', 'ГЦЦ': 'АЛА', 'ГЦА': 'АЛА', 'ГЦГ': 'АЛА',
    'УАУ': 'ТИР', 'УАЦ': 'ТИР', 'УАА': 'СТОП', 'УАГ': 'СТОП',
    'ЦАУ': 'ГИС', 'ЦАЦ': 'ГИС', 'ЦАА': 'ГЛН', 'ЦАГ': 'ГЛН',
    'ААУ': 'АСН', 'ААЦ': 'АСН', 'ААА': 'ЛИЗ', 'ААГ': 'ЛИЗ',
    'ГАУ': 'АСП', 'ГАЦ': 'АСП', 'ГАА': 'ГЛУ', 'ГАГ': 'ГЛУ',
    'УГУ': 'ЦИС', 'УГЦ': 'ЦИС', 'УГА': 'СТОП', 'УГГ': 'ТРИ',
    'ЦГУ': 'АРГ', 'ЦГЦ': 'АРГ', 'ЦГА': 'АРГ', 'ЦГГ': 'АРГ',
    'АГУ': 'СЕР', 'АГЦ': 'СЕР', 'АГА': 'АРГ', 'АГГ': 'АРГ',
    'ГГУ': 'ГЛИ', 'ГГЦ': 'ГЛИ', 'ГГА': 'ГЛИ', 'ГГГ': 'ГЛИ',
  };

  const BASES = ['У', 'Ц', 'А', 'Г'];

  function renderGeneticTableModal() {
    ensureStyles();
    const existing = document.getElementById('gen-table-modal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.className = 'gen-modal-overlay';
    overlay.id = 'gen-table-modal';

    let tableRows = '';
    BASES.forEach(first => {
      BASES.forEach((third, tIdx) => {
        tableRows += '<tr>';
        if (tIdx === 0) {
          tableRows += `<th rowspan="4" style="vertical-align:middle;font-size:1.1rem;background:rgba(99,102,241,0.08)">${first}</th>`;
        }
        BASES.forEach(second => {
          const codon = `${first}${second}${third}`;
          const aa = GENETIC_MAP[codon] || '—';
          tableRows += `<td class="codon-cell" data-codon="${codon}" data-aa="${aa}"><strong>${codon}</strong>: ${aa}</td>`;
        });
        tableRows += `<th style="background:rgba(99,102,241,0.08)">${third}</th>`;
        tableRows += '</tr>';
      });
    });

    overlay.innerHTML = `
      <div class="gen-modal-card" role="dialog" aria-modal="true">
        <div class="gen-modal-head">
          <div class="gen-modal-title"><i class="ti ti-table"></i> Таблица генетического кода (иРНК 5' → 3')</div>
          <button type="button" class="btn-ghost" id="close-gen-modal" style="font-size:1.2rem;padding:4px 8px"><i class="ti ti-x"></i></button>
        </div>
        <div class="gen-search-bar">
          <input type="text" class="gen-search-input" id="gen-search-input" placeholder="Поиск по кодону (например: АУГ) или аминокислоте (например: МЕТ)..." autocomplete="off" />
        </div>
        <div class="gen-table-wrap">
          <table class="gen-table">
            <thead>
              <tr>
                <th rowspan="2" style="vertical-align:middle">1-я база (5')</th>
                <th colspan="4">Вторая база</th>
                <th rowspan="2" style="vertical-align:middle">3-я база (3')</th>
              </tr>
              <tr>
                <th>У</th>
                <th>Ц</th>
                <th>А</th>
                <th>Г</th>
              </tr>
            </thead>
            <tbody>
              ${tableRows}
            </tbody>
          </table>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);

    const closeBtn = overlay.querySelector('#close-gen-modal');
    const close = () => overlay.remove();
    closeBtn.onclick = close;
    overlay.onclick = (e) => { if (e.target === overlay) close(); };
    window.addEventListener('keydown', function onEsc(e) {
      if (e.key === 'Escape') {
        close();
        window.removeEventListener('keydown', onEsc);
      }
    });

    const searchInput = overlay.querySelector('#gen-search-input');
    const cells = overlay.querySelectorAll('.codon-cell');
    searchInput.oninput = () => {
      const q = searchInput.value.trim().toUpperCase();
      cells.forEach(cell => {
        const codon = cell.dataset.codon;
        const aa = cell.dataset.aa;
        const match = q && (codon.includes(q) || aa.includes(q));
        cell.classList.toggle('highlight', !!match);
      });
    };
  }

  // 2. Конструктор нуклеотида
  function renderNucleotideBuilder(container, condition, onChange) {
    ensureStyles();
    container.innerHTML = '';

    const wrap = document.createElement('div');
    wrap.className = 'bio-widget-wrap';

    const targetName = condition.target || 'Нуклеотид';
    const state = {
      base: null,
      sugar: null,
      has_phosphate: false
    };

    wrap.innerHTML = `
      <div class="bio-widget-title"><i class="ti ti-puzzle"></i> Конструктор нуклеотида: ${escapeHtml(targetName)}</div>
      <div class="bio-widget-desc">Соберите целевой нуклеотид из трех компонентов: азотистого основания, углевода (пентозы) и остатка фосфорной кислоты. Перетащите элементы в слоты или кликните по компоненту, затем по нужному слоту.</div>

      <div class="bio-palette" id="palette-phos">
        <div class="bio-palette-label">1. Фосфатная группа:</div>
        <div class="bio-chip bio-chip-phos" draggable="true" data-type="phosphate" data-val="фосфат"><i class="ti ti-circle-dot"></i> Остаток фосфорной кислоты (PO₄³⁻)</div>
      </div>

      <div class="bio-palette" id="palette-sugar">
        <div class="bio-palette-label">2. Углевод (пентоза):</div>
        <div class="bio-chip bio-chip-sugar" draggable="true" data-type="sugar" data-val="рибоза"><i class="ti ti-polygon"></i> Рибоза (РНК)</div>
        <div class="bio-chip bio-chip-sugar" draggable="true" data-type="sugar" data-val="дезоксирибоза"><i class="ti ti-polygon"></i> Дезоксирибоза (ДНК)</div>
      </div>

      <div class="bio-palette" id="palette-base">
        <div class="bio-palette-label">3. Азотистые основания:</div>
        <div class="bio-chip bio-chip-base bio-chip-nuc" draggable="true" data-type="base" data-val="А" title="Аденин">А</div>
        <div class="bio-chip bio-chip-base bio-chip-nuc" draggable="true" data-type="base" data-val="Т" title="Тимин (ДНК)">Т</div>
        <div class="bio-chip bio-chip-base bio-chip-nuc" draggable="true" data-type="base" data-val="Г" title="Гуанин">Г</div>
        <div class="bio-chip bio-chip-base bio-chip-nuc" draggable="true" data-type="base" data-val="Ц" title="Цитозин">Ц</div>
        <div class="bio-chip bio-chip-base bio-chip-nuc" draggable="true" data-type="base" data-val="У" title="Урацил (РНК)">У</div>
      </div>

      <div class="bio-dock">
        <div class="bio-dock-slot" data-slot="phosphate">
          <div class="bio-slot-title">Фосфат (5'-конец)</div>
          <div class="bio-slot-val" id="slot-val-phosphate">—</div>
        </div>
        <div class="bio-dock-slot" data-slot="sugar">
          <div class="bio-slot-title">Углевод (пентоза)</div>
          <div class="bio-slot-val" id="slot-val-sugar">—</div>
        </div>
        <div class="bio-dock-slot" data-slot="base">
          <div class="bio-slot-title">Азотистое основание (1'-C)</div>
          <div class="bio-slot-val" id="slot-val-base">—</div>
        </div>
      </div>
    `;

    container.appendChild(wrap);

    let selectedChip = null;

    function notify() {
      if (typeof onChange === 'function') {
        onChange({
          sugar: state.sugar,
          base: state.base,
          has_phosphate: state.has_phosphate,
          phosphate: state.has_phosphate
        });
      }
    }

    function updateSlots() {
      const phosSlot = wrap.querySelector('[data-slot="phosphate"]');
      const sugarSlot = wrap.querySelector('[data-slot="sugar"]');
      const baseSlot = wrap.querySelector('[data-slot="base"]');

      phosSlot.classList.toggle('filled', state.has_phosphate);
      phosSlot.querySelector('.bio-slot-val').textContent = state.has_phosphate ? 'Фосфат ✓' : '—';

      sugarSlot.classList.toggle('filled', !!state.sugar);
      sugarSlot.querySelector('.bio-slot-val').textContent = state.sugar || '—';

      baseSlot.classList.toggle('filled', !!state.base);
      baseSlot.querySelector('.bio-slot-val').textContent = state.base || '—';

      notify();
    }

    // Drag-and-drop
    wrap.querySelectorAll('.bio-chip').forEach(chip => {
      chip.addEventListener('dragstart', (e) => {
        e.dataTransfer.setData('text/plain', JSON.stringify({
          type: chip.dataset.type,
          val: chip.dataset.val
        }));
      });
      chip.addEventListener('click', () => {
        if (selectedChip === chip) {
          chip.classList.remove('active-selected');
          selectedChip = null;
        } else {
          wrap.querySelectorAll('.bio-chip').forEach(c => c.classList.remove('active-selected'));
          chip.classList.add('active-selected');
          selectedChip = chip;
        }
      });
    });

    wrap.querySelectorAll('.bio-dock-slot').forEach(slot => {
      slot.addEventListener('dragover', (e) => {
        e.preventDefault();
        slot.classList.add('drag-over');
      });
      slot.addEventListener('dragleave', () => slot.classList.remove('drag-over'));
      slot.addEventListener('drop', (e) => {
        e.preventDefault();
        slot.classList.remove('drag-over');
        try {
          const data = JSON.parse(e.dataTransfer.getData('text/plain'));
          placeItem(slot.dataset.slot, data.type, data.val);
        } catch (_) {}
      });
      slot.addEventListener('click', () => {
        if (selectedChip) {
          placeItem(slot.dataset.slot, selectedChip.dataset.type, selectedChip.dataset.val);
          selectedChip.classList.remove('active-selected');
          selectedChip = null;
        } else {
          // Clear slot on click if already filled
          if (slot.dataset.slot === 'phosphate') state.has_phosphate = false;
          if (slot.dataset.slot === 'sugar') state.sugar = null;
          if (slot.dataset.slot === 'base') state.base = null;
          updateSlots();
        }
      });
    });

    function placeItem(slotType, chipType, val) {
      if (slotType === 'phosphate' && chipType === 'phosphate') {
        state.has_phosphate = true;
      } else if (slotType === 'sugar' && chipType === 'sugar') {
        state.sugar = val;
      } else if (slotType === 'base' && chipType === 'base') {
        state.base = val;
      }
      updateSlots();
    }
  }

  // 3. Сборка цепи нуклеотидов (5' -> 3')
  function renderChainAssembly(container, condition, onChange) {
    ensureStyles();
    container.innerHTML = '';

    const wrap = document.createElement('div');
    wrap.className = 'bio-widget-wrap';

    const targetSeq = condition.target_sequence || 'АТГЦ';
    const tmplSeq = condition.template_sequence || '';
    const length = targetSeq.length || 4;
    const currentChain = new Array(length).fill('');

    let tmplHtml = '';
    if (tmplSeq) {
      tmplHtml = `
        <div style="font-size:0.84rem;color:var(--muted,#9daac4);margin-bottom:4px">Матричная цепь ДНК (3' → 5'):</div>
        <div class="bio-chain-row" style="opacity:0.85">
          <span class="bio-chain-end">3'</span>
          ${tmplSeq.split('').map(n => `<div class="bio-chain-slot filled" style="cursor:default">${escapeHtml(n)}</div>`).join('')}
          <span class="bio-chain-end">5'</span>
        </div>
      `;
    }

    wrap.innerHTML = `
      <div class="bio-widget-title"><i class="ti ti-link"></i> Сборка полинуклеотидной цепи (5' → 3')</div>
      <div class="bio-widget-desc">Соберите комплементарную цепь в направлении от 5'-конца к 3'-концу. Кликните или перетащите нуклеотид в соответствующую позицию цепочки. Клик по позиции очищает её.</div>
      ${tmplHtml}
      <div style="font-size:0.84rem;color:var(--muted,#9daac4);margin-top:8px">Собираемая комплементарная цепь (5' → 3'):</div>
      <div class="bio-chain-row" id="assembly-row">
        <span class="bio-chain-end">5'</span>
        ${Array.from({ length }).map((_, i) => `
          <div class="bio-chain-slot" data-index="${i}">
            <span class="slot-char">—</span>
            <span class="slot-idx">${i + 1}</span>
          </div>
        `).join('')}
        <span class="bio-chain-end">3'</span>
      </div>

      <div class="bio-palette" id="chain-nuc-palette">
        <div class="bio-palette-label">Банк нуклеотидов:</div>
        <div class="bio-chip bio-chip-nuc" draggable="true" data-nuc="А">А</div>
        <div class="bio-chip bio-chip-nuc" draggable="true" data-nuc="Т">Т</div>
        <div class="bio-chip bio-chip-nuc" draggable="true" data-nuc="Г">Г</div>
        <div class="bio-chip bio-chip-nuc" draggable="true" data-nuc="Ц">Ц</div>
        <div class="bio-chip bio-chip-nuc" draggable="true" data-nuc="У">У</div>
      </div>
      <div class="bio-bonds-indicator">
        <span><i class="ti ti-info-circle"></i> Водородные связи: А=Т (2 связи), Г≡Ц (3 связи)</span>
      </div>
    `;

    container.appendChild(wrap);

    let activeNuc = null;

    function notify() {
      if (typeof onChange === 'function') {
        onChange(currentChain.join(''));
      }
    }

    function updateSlots() {
      const slots = wrap.querySelectorAll('.bio-chain-slot[data-index]');
      slots.forEach((slot, i) => {
        const val = currentChain[i];
        slot.classList.toggle('filled', !!val);
        slot.querySelector('.slot-char').textContent = val || '—';
      });
      notify();
    }

    wrap.querySelectorAll('.bio-chip[data-nuc]').forEach(chip => {
      chip.addEventListener('dragstart', (e) => {
        e.dataTransfer.setData('text/plain', chip.dataset.nuc);
      });
      chip.addEventListener('click', () => {
        if (activeNuc === chip.dataset.nuc) {
          chip.classList.remove('active-selected');
          activeNuc = null;
        } else {
          wrap.querySelectorAll('.bio-chip').forEach(c => c.classList.remove('active-selected'));
          chip.classList.add('active-selected');
          activeNuc = chip.dataset.nuc;
          const emptyIdx = currentChain.findIndex(c => !c);
          if (emptyIdx !== -1) {
            currentChain[emptyIdx] = activeNuc;
            updateSlots();
          }
        }
      });
    });

    wrap.querySelectorAll('.bio-chain-slot[data-index]').forEach(slot => {
      const idx = parseInt(slot.dataset.index, 10);
      slot.addEventListener('dragover', (e) => {
        e.preventDefault();
        slot.classList.add('drag-over');
      });
      slot.addEventListener('dragleave', () => slot.classList.remove('drag-over'));
      slot.addEventListener('drop', (e) => {
        e.preventDefault();
        slot.classList.remove('drag-over');
        const nuc = e.dataTransfer.getData('text/plain');
        if (nuc) {
          currentChain[idx] = nuc;
          updateSlots();
        }
      });
      slot.addEventListener('click', () => {
        if (activeNuc) {
          currentChain[idx] = activeNuc;
          updateSlots();
        } else {
          currentChain[idx] = '';
          updateSlots();
        }
      });
    });
  }

  // 4. Скручивание тРНК в трилистник
  function renderCloverleafFolding(container, condition, onChange) {
    ensureStyles();
    container.innerHTML = '';

    const wrap = document.createElement('div');
    wrap.className = 'bio-widget-wrap';

    const trnaName = condition.trna_name || 'тРНК';
    const amino = condition.amino_acid || 'МЕТ';
    const targetAnticodon = condition.anticodon || 'УАЦ';
    let isFolded = false;
    let anticodonLetters = ['', '', ''];

    wrap.innerHTML = `
      <div class="bio-widget-title"><i class="ti ti-clover"></i> Вторичная структура ${escapeHtml(trnaName)} («Трилистник»)</div>
      <div class="bio-widget-desc">Первичная цепочка тРНК скручивается во вторичную структуру клеверного листа за счет спаривания комплементарных участков. Спарьте цепь и укажите антикодон в центральной петле.</div>

      <div class="bio-cloverleaf-box">
        <div class="bio-clover-diagram" id="clover-visual">
          <svg viewBox="0 0 320 280" width="100%" height="220" style="overflow:visible">
            <!-- Акцепторный стебель -->
            <path id="stem-acceptor" d="M 150 20 L 150 70 M 170 20 L 170 70" stroke="var(--primary,#6366f1)" stroke-width="4" stroke-linecap="round" fill="none" />
            <text x="145" y="14" fill="var(--text,#fff)" font-size="12" text-anchor="end">5'</text>
            <text x="175" y="14" fill="var(--accent,#4ade80)" font-weight="700" font-size="12">3'-ЦЦА (${escapeHtml(amino)})</text>

            <!-- D-петля (левая) -->
            <path id="loop-d" d="M 150 90 Q 70 80 70 120 Q 70 160 140 130" stroke="var(--primary,#6366f1)" stroke-width="3" fill="none" opacity="0.4" />
            <text x="60" y="125" fill="var(--muted,#9daac4)" font-size="11" text-anchor="end">D-петля</text>

            <!-- TΨC-петля (правая) -->
            <path id="loop-t" d="M 170 90 Q 250 80 250 120 Q 250 160 180 130" stroke="var(--primary,#6366f1)" stroke-width="3" fill="none" opacity="0.4" />
            <text x="260" y="125" fill="var(--muted,#9daac4)" font-size="11">ТΨС-петля</text>

            <!-- Антикодоновая петля (центральная) -->
            <path id="loop-anticodon" d="M 140 140 L 140 190 Q 140 240 160 240 Q 180 240 180 190 L 180 140" stroke="var(--primary,#6366f1)" stroke-width="4" fill="none" opacity="0.4" />
            <circle cx="160" cy="240" r="16" fill="rgba(99,102,241,0.2)" stroke="var(--accent,#4ade80)" stroke-width="2" id="anticodon-circle" />
            <text x="160" y="244" text-anchor="middle" font-weight="800" font-size="12" fill="var(--text,#fff)" id="anticodon-svg-text">???</text>
            <text x="160" y="272" text-anchor="middle" font-size="11" fill="var(--muted,#9daac4)">Антикодон</text>
          </svg>
        </div>

        <div style="display:flex;flex-direction:column;align-items:center;gap:12px">
          <button type="button" class="bio-clover-fold-btn" id="btn-fold-clover">
            <i class="ti ti-refresh"></i> <span id="fold-btn-text">Скрутить цепь в трилистник (образовать водородные связи)</span>
          </button>

          <div style="text-align:center">
            <div style="font-size:0.85rem;color:var(--muted,#9daac4);margin-bottom:6px">Укажите 3 буквы антикодона тРНК:</div>
            <div class="bio-anticodon-inputs">
              <input type="text" maxlength="1" class="bio-anticodon-triplet-input" data-idx="0" placeholder="—" />
              <input type="text" maxlength="1" class="bio-anticodon-triplet-input" data-idx="1" placeholder="—" />
              <input type="text" maxlength="1" class="bio-anticodon-triplet-input" data-idx="2" placeholder="—" />
            </div>
          </div>
        </div>
      </div>
    `;

    container.appendChild(wrap);

    const foldBtn = wrap.querySelector('#btn-fold-clover');
    const foldText = wrap.querySelector('#fold-btn-text');
    const dLoop = wrap.querySelector('#loop-d');
    const tLoop = wrap.querySelector('#loop-t');
    const antiLoop = wrap.querySelector('#loop-anticodon');
    const svgText = wrap.querySelector('#anticodon-svg-text');

    function notify() {
      if (typeof onChange === 'function') {
        const fullAnticodon = anticodonLetters.join('').toUpperCase();
        onChange({
          anticodon: fullAnticodon,
          paired: isFolded,
          amino_acid: amino
        });
      }
    }

    foldBtn.onclick = () => {
      isFolded = !isFolded;
      if (isFolded) {
        dLoop.setAttribute('opacity', '1');
        tLoop.setAttribute('opacity', '1');
        antiLoop.setAttribute('opacity', '1');
        dLoop.setAttribute('stroke', 'var(--accent,#4ade80)');
        tLoop.setAttribute('stroke', 'var(--accent,#4ade80)');
        antiLoop.setAttribute('stroke', 'var(--accent,#4ade80)');
        foldBtn.style.background = 'var(--accent,#4ade80)';
        foldText.textContent = 'Вторичная структура собрана ✓';
      } else {
        dLoop.setAttribute('opacity', '0.4');
        tLoop.setAttribute('opacity', '0.4');
        antiLoop.setAttribute('opacity', '0.4');
        dLoop.setAttribute('stroke', 'var(--primary,#6366f1)');
        tLoop.setAttribute('stroke', 'var(--primary,#6366f1)');
        antiLoop.setAttribute('stroke', 'var(--primary,#6366f1)');
        foldBtn.style.background = 'var(--primary,#6366f1)';
        foldText.textContent = 'Скрутить цепь в трилистник (образовать водородные связи)';
      }
      notify();
    };

    const inputs = wrap.querySelectorAll('.bio-anticodon-triplet-input');
    inputs.forEach((input, i) => {
      input.oninput = () => {
        const val = input.value.trim().toUpperCase();
        input.value = val;
        anticodonLetters[i] = val;
        svgText.textContent = anticodonLetters.map(c => c || '?').join('');
        if (val && i < 2) inputs[i + 1].focus();
        notify();
      };
      input.onkeydown = (e) => {
        if (e.key === 'Backspace' && !input.value && i > 0) {
          inputs[i - 1].focus();
        }
      };
    });
  }

  // Экспорт в глобальный объект
  window.BioInteractive = {
    renderGeneticTableModal,
    renderNucleotideBuilder,
    renderChainAssembly,
    renderCloverleafFolding,
  };
})();
