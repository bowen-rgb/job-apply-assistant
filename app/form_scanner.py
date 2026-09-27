from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .agent_policy import field_is_sensitive, field_is_captcha_or_mfa, button_kind


def instrument_and_scan(page) -> dict[str, Any]:
    """Return a privacy-reduced, stable-id form snapshot for the browser agent.

    Inspired by the field-scanning approach in the MIT-licensed devdattatalele/auto-apply
    scanner, but rewritten for this project's Python/Playwright safety model.
    """
    raw = page.evaluate(
        r'''() => {
          if (!window.__jaaCounter) window.__jaaCounter = 1;
          const nextId = (prefix) => `${prefix}-${window.__jaaCounter++}`;
          const text = (v) => String(v || '').replace(/\s+/g, ' ').trim();
          const visible = (el) => {
            const s = getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0;
          };
          const labelFor = (el) => {
            const bits = [];
            if (el.id) {
              try { const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l) bits.push(text(l.innerText)); } catch {}
            }
            const pl = el.closest('label'); if (pl) bits.push(text(pl.innerText));
            const aria = el.getAttribute('aria-label'); if (aria) bits.push(text(aria));
            const labelled = el.getAttribute('aria-labelledby');
            if (labelled) {
              for (const id of labelled.split(/\s+/)) { const x=document.getElementById(id); if(x) bits.push(text(x.innerText)); }
            }
            if (el.placeholder) bits.push(text(el.placeholder));
            if (el.name) bits.push(text(el.name));
            return [...new Set(bits.filter(Boolean))].join(' | ').slice(0, 350);
          };
          const answered = (el, type) => {
            try {
              if (type === 'checkbox' || type === 'radio') return !!el.checked;
              if (type === 'file') return !!(el.files && el.files.length);
              if (el.tagName.toLowerCase() === 'select') return !!el.value;
              if (el.getAttribute('role') === 'combobox') {
                const v = text(el.getAttribute('aria-valuetext') || el.getAttribute('data-value') || el.value || el.textContent);
                return !!v && !/select|choose|choisir|sélectionner/i.test(v);
              }
              return !!String(el.value || '').trim();
            } catch { return false; }
          };
          const fields=[];
          for (const el of document.querySelectorAll('input, textarea, select, [role="combobox"]')) {
            if (!visible(el)) continue;
            const tag=el.tagName.toLowerCase();
            let type=(el.getAttribute('type') || (tag==='select'?'select':tag)).toLowerCase();
            if (['hidden','submit','button','image','reset','password'].includes(type)) continue;
            let id=el.getAttribute('data-jaa-id'); if(!id){id=nextId('field');el.setAttribute('data-jaa-id',id)}
            const required=!!(el.required || el.getAttribute('aria-required')==='true');
            const item={
              field_id:id,
              label:labelFor(el),
              name:text(el.getAttribute('name')).slice(0,180),
              dom_id:text(el.id).slice(0,180),
              type,
              tag,
              role:text(el.getAttribute('role')).slice(0,80),
              required,
              answered:answered(el,type),
              accept:text(el.getAttribute('accept')).slice(0,180),
              autocomplete:text(el.getAttribute('autocomplete')).slice(0,120),
              options:[]
            };
            if(tag==='select') item.options=[...el.options].map(o=>text(o.textContent)).filter(Boolean).slice(0,80);
            fields.push(item);
          }
          const buttons=[];
          for (const el of document.querySelectorAll('button, input[type="submit"], input[type="button"], [role="button"], a.btn, a.button')) {
            if (!visible(el)) continue;
            let id=el.getAttribute('data-jaa-id'); if(!id){id=nextId('button');el.setAttribute('data-jaa-id',id)}
            const txt=text(el.innerText || el.value || el.getAttribute('aria-label'));
            if (!txt || txt.length>180) continue;
            buttons.push({button_id:id,text:txt.slice(0,180),disabled:!!el.disabled});
          }
          return {fields,buttons,title:document.title,body_excerpt:text(document.body?.innerText).slice(0,3500)};
        }'''
    )

    fields = []
    for f in raw.get('fields', []):
        item = dict(f)
        item['sensitive_or_legal'] = field_is_sensitive(item)
        item['captcha_or_mfa'] = field_is_captcha_or_mfa(item)
        # Never return already-typed values.
        fields.append(item)

    buttons = []
    for b in raw.get('buttons', []):
        x = dict(b)
        x['kind'] = button_kind(x.get('text', ''))
        buttons.append(x)

    return {
        'page_url': page.url,
        'page_title': raw.get('title', ''),
        'captured_at': datetime.now(timezone.utc).isoformat(),
        'privacy_note': 'No typed field values are included. Only labels, types, options, required/answered state and button text are sent to the planner.',
        'fields': fields,
        'buttons': buttons,
        'body_excerpt': raw.get('body_excerpt', ''),
    }


def field_locator(page, field_id: str):
    return page.locator(f'[data-jaa-id="{field_id}"]').first


def button_locator(page, button_id: str):
    return page.locator(f'[data-jaa-id="{button_id}"]').first
