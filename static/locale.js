/* Local UI translations. Job descriptions and user-entered profile data stay in their original language. */
const Locale = (() => {
  const supported = ['zh', 'fr', 'en', 'de', 'es', 'pt'];
  const browser = (navigator.language || 'fr').split('-')[0].toLowerCase();
  const saved = localStorage.getItem('jaa-ui-language');
  let language = supported.includes(saved) ? saved : (supported.includes(browser) ? browser : 'fr');
  const catalogs = {};
  const originals = new WeakMap();
  const attributes = new WeakMap();
  let pending = false;

  const ready = Promise.all(supported.map(async code => {
    try {
      const response = await fetch(`/static/locales/${code}.json`);
      if (!response.ok) throw new Error(`Missing locale ${code}`);
      catalogs[code] = await response.json();
    } catch (error) {
      catalogs[code] = {};
      console.warn(error);
    }
  }));

  function t(key) {
    return catalogs[language]?.[key] || catalogs.fr?.[key] || key;
  }

  function translateNode(node) {
    if (node.parentElement?.closest('script,style,code,pre,#languageSelect,.brand,#sourceSelect,.snippet,.reason,.title,.company,.source,.fact,.review-summary,.pipeline-card b,.queue-item b')) return;
    const previous = originals.get(node);
    const current = node.nodeValue;
    const source = previous && current === previous.last ? previous.source : current;
    const trimmed = source.trim();
    if (!trimmed || !catalogs.fr?.[trimmed]) return;
    const translated = source.replace(trimmed, t(trimmed));
    originals.set(node, {source, last: translated});
    if (current !== translated) node.nodeValue = translated;
  }

  function translateAttributes(element) {
    let savedAttrs = attributes.get(element) || {};
    for (const attr of ['placeholder', 'title', 'aria-label']) {
      if (!element.hasAttribute(attr)) continue;
      const value = element.getAttribute(attr);
      const previous = savedAttrs[attr];
      const source = previous && value === previous.last ? previous.source : value;
      if (!catalogs.fr?.[source]) continue;
      const translated = t(source);
      savedAttrs[attr] = {source, last: translated};
      if (value !== translated) element.setAttribute(attr, translated);
    }
    attributes.set(element, savedAttrs);
  }

  function apply(root = document.body) {
    document.documentElement.lang = language === 'zh' ? 'zh-CN' : language;
    document.title = `Job Apply Assistant · ${t('Offres')}`;
    const selector = document.getElementById('languageSelect');
    if (selector) selector.value = language;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) translateNode(walker.currentNode);
    if (root.nodeType === Node.ELEMENT_NODE) translateAttributes(root);
    root.querySelectorAll?.('[placeholder],[title],[aria-label]').forEach(translateAttributes);
  }

  function schedule() {
    if (pending) return;
    pending = true;
    queueMicrotask(() => { pending = false; apply(); });
  }

  function setLanguage(code) {
    if (!supported.includes(code)) return;
    language = code;
    localStorage.setItem('jaa-ui-language', code);
    apply();
    document.dispatchEvent(new CustomEvent('localechange'));
  }

  ready.then(() => {
    apply();
    document.getElementById('languageSelect')?.addEventListener('change', event => setLanguage(event.target.value));
    new MutationObserver(schedule).observe(document.body, {childList: true, characterData: true, attributes: true, subtree: true, attributeFilter: ['placeholder', 'title', 'aria-label']});
  });
  return {t, ready, apply, setLanguage, get language() { return language; }};
})();
