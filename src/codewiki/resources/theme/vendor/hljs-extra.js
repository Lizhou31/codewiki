/* Small highlight.js grammars not in the common CDN bundle.
 * devicetree (.dts/.dtsi/.overlay) and kconfig fragments (.conf / Kconfig).
 * Written for highlight.js 11.x; MIT like the rest of the vendored assets. */
(function () {
  if (!window.hljs) return;

  hljs.registerLanguage("dts", function (hljs) {
    return {
      name: "Devicetree",
      aliases: ["devicetree", "overlay", "dtsi"],
      contains: [
        hljs.C_LINE_COMMENT_MODE,
        hljs.C_BLOCK_COMMENT_MODE,
        hljs.QUOTE_STRING_MODE,
        { className: "meta", begin: /^\s*#\s*(include|define|undef|if|ifdef|ifndef|elif|else|endif)\b/, end: /$/,
          contains: [hljs.QUOTE_STRING_MODE, { className: "string", begin: /</, end: />/ }] },
        { className: "symbol", begin: /&[A-Za-z_][\w\-]*/ },
        { className: "title.class", begin: /\/(?=\s*\{)/ },
        { className: "title.function", begin: /[A-Za-z_][\w\-,.+]*(@[0-9a-fA-F,]+)?(?=\s*\{)/ },
        { className: "title.class", begin: /[A-Za-z_][\w\-]*(?=\s*:)/ },
        { className: "attr", begin: /[A-Za-z_#][\w\-,.+?#]*(?=\s*(=|;))/ },
        { className: "number", begin: /\b(0[xX][0-9a-fA-F]+|\d+)\b/ },
        { className: "punctuation", begin: /[<>;{}=]/ }
      ]
    };
  });

  hljs.registerLanguage("kconfig", function (hljs) {
    return {
      name: "Kconfig",
      aliases: ["conf", "defconfig"],
      contains: [
        hljs.HASH_COMMENT_MODE,
        hljs.QUOTE_STRING_MODE,
        { className: "keyword", begin: /^\s*(config|menuconfig|choice|endchoice|menu|endmenu|if|endif|source|rsource|osource|depends on|select|imply|default|help|prompt|range|bool|int|hex|string|tristate|def_bool|def_int|def_hex|def_string|def_tristate|visible if|option|comment)\b/ },
        { className: "variable", begin: /\b(CONFIG|SB_CONFIG)_[A-Za-z0-9_]+/ },
        { className: "number", begin: /\b(0[xX][0-9a-fA-F]+|\d+)\b/ },
        { className: "literal", begin: /(?<==)(y|n|m)\b/ },
        { className: "operator", begin: /=/ }
      ]
    };
  });
  // hljs "ini" is already registered by the bundle; alias our conf class to kconfig
  try { hljs.registerAliases(["conf"], { languageName: "kconfig" }); } catch (e) {}
})();
