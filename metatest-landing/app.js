/* MetaTest 官网 · 共享脚本（复制命令 / 语言 tab / toast） */
(function () {
  function toast(msg) {
    var el = document.getElementById('toast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'toast';
      el.className = 'toast';
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.classList.add('show');
    clearTimeout(el._t);
    el._t = setTimeout(function () { el.classList.remove('show'); }, 1800);
  }

  // 为每个代码块注入“复制”按钮
  document.querySelectorAll('.code-wrap').forEach(function (wrap) {
    if (wrap.querySelector('.copy-btn')) return;
    var pre = wrap.querySelector('pre');
    if (!pre) return;
    var btn = document.createElement('button');
    btn.className = 'copy-btn';
    btn.type = 'button';
    btn.textContent = '复制';
    btn.setAttribute('aria-label', '复制命令');
    btn.addEventListener('click', function () {
      var text = pre.innerText;
      function done() {
        btn.textContent = '已复制';
        btn.classList.add('copied');
        toast('命令已复制到剪贴板');
        setTimeout(function () { btn.textContent = '复制'; btn.classList.remove('copied'); }, 1600);
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done).catch(fallback);
      } else { fallback(); }
      function fallback() {
        var ta = document.createElement('textarea');
        ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
        document.body.appendChild(ta); ta.select();
        try { document.execCommand('copy'); done(); } catch (e) { toast('复制失败，请手动选择'); }
        document.body.removeChild(ta);
      }
    });
    wrap.appendChild(btn);
  });

  // 语言 tab 切换
  document.querySelectorAll('[data-tab-group]').forEach(function (group) {
    var tabs = group.querySelectorAll('.tab');
    var panels = document.querySelectorAll('[data-panel="' + group.dataset.tabGroup + '"]');
    tabs.forEach(function (tab) {
      tab.addEventListener('click', function () {
        var target = tab.dataset.tab;
        tabs.forEach(function (t) { t.classList.toggle('active', t === tab); });
        panels.forEach(function (p) { p.classList.toggle('active', p.dataset.panelValue === target); });
      });
    });
  });

  // 高亮当前页导航
  var path = location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.nav-links a[data-page]').forEach(function (a) {
    if (a.dataset.page === path) a.classList.add('active');
  });
})();
