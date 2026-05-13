// Tiny inline SVG icons for AGORA. Each takes optional `size`/`stroke`.
// Stroke-based to match the editorial / hairline aesthetic.

const AIcon = ({ d, size = 16, stroke = 1.5, fill = "none", style }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
       strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" style={style}>
    {d}
  </svg>
);

const I = {
  home:    (p) => <AIcon {...p} d={<><path d="M3 11.5 12 4l9 7.5"/><path d="M5 10v10h14V10"/></>}/>,
  spark:  (p) => <AIcon {...p} d={<><path d="M12 3v4"/><path d="M12 17v4"/><path d="M3 12h4"/><path d="M17 12h4"/><path d="M5.5 5.5 8 8"/><path d="M16 16l2.5 2.5"/><path d="M5.5 18.5 8 16"/><path d="M16 8l2.5-2.5"/></>}/>,
  list:    (p) => <AIcon {...p} d={<><path d="M8 6h12"/><path d="M8 12h12"/><path d="M8 18h12"/><circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/></>}/>,
  grid:    (p) => <AIcon {...p} d={<><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>}/>,
  bot:     (p) => <AIcon {...p} d={<><rect x="4" y="7" width="16" height="12" rx="3"/><path d="M12 3v4"/><circle cx="9" cy="13" r="1"/><circle cx="15" cy="13" r="1"/><path d="M2 14v2"/><path d="M22 14v2"/></>}/>,
  pulse:   (p) => <AIcon {...p} d={<><path d="M3 12h4l2-6 4 12 2-6h6"/></>}/>,
  team:    (p) => <AIcon {...p} d={<><circle cx="9" cy="8" r="3"/><circle cx="17" cy="9" r="2.2"/><path d="M3 20c.5-3.5 3-5 6-5s5.5 1.5 6 5"/><path d="M15 14c2 .2 4 1.4 4.6 4"/></>}/>,
  search:  (p) => <AIcon {...p} d={<><circle cx="11" cy="11" r="6"/><path d="M20 20l-4-4"/></>}/>,
  bell:    (p) => <AIcon {...p} d={<><path d="M6 16V11a6 6 0 1 1 12 0v5l1.5 2H4.5L6 16z"/><path d="M10 20a2 2 0 0 0 4 0"/></>}/>,
  arch:    (p) => <AIcon {...p} d={<><path d="M5 20V10a7 7 0 0 1 14 0v10"/><path d="M3 20h18"/></>}/>,
  agora:   (p) => <AIcon {...p} d={<><circle cx="12" cy="12" r="9"/><path d="M3.5 12h17"/><path d="M12 3.5c2.5 2.5 3.8 5.5 3.8 8.5s-1.3 6-3.8 8.5"/><path d="M12 3.5c-2.5 2.5-3.8 5.5-3.8 8.5s1.3 6 3.8 8.5"/></>}/>,
  send:    (p) => <AIcon {...p} d={<><path d="M4 12 20 4l-3 16-5-7-8-1z"/></>}/>,
  paperclip:(p) => <AIcon {...p} d={<><path d="M20 11.5 12 19.5a5 5 0 0 1-7-7L13 5a3.5 3.5 0 0 1 5 5l-8 8a2 2 0 0 1-3-3l7-7"/></>}/>,
  cmd:     (p) => <AIcon {...p} d={<><path d="M9 6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3z"/></>}/>,
  chev:    (p) => <AIcon {...p} d={<><path d="m9 6 6 6-6 6"/></>}/>,
  chevd:   (p) => <AIcon {...p} d={<><path d="m6 9 6 6 6-6"/></>}/>,
  arrowR:  (p) => <AIcon {...p} d={<><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></>}/>,
  check:   (p) => <AIcon {...p} d={<><path d="M5 12.5 10 17l9-10"/></>}/>,
  warn:    (p) => <AIcon {...p} d={<><path d="M12 4 22 20H2L12 4z"/><path d="M12 11v4"/><circle cx="12" cy="18" r=".6" fill="currentColor"/></>}/>,
  shield:  (p) => <AIcon {...p} d={<><path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6l-8-3z"/></>}/>,
  zap:     (p) => <AIcon {...p} d={<><path d="m13 3-9 12h7l-1 6 9-12h-7l1-6z"/></>}/>,
  dot:     (p) => <AIcon {...p} d={<circle cx="12" cy="12" r="3" fill="currentColor"/>}/>,
  plus:    (p) => <AIcon {...p} d={<><path d="M12 5v14"/><path d="M5 12h14"/></>}/>,
  copy:    (p) => <AIcon {...p} d={<><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/></>}/>,
  more:    (p) => <AIcon {...p} d={<><circle cx="6" cy="12" r="1.2" fill="currentColor"/><circle cx="12" cy="12" r="1.2" fill="currentColor"/><circle cx="18" cy="12" r="1.2" fill="currentColor"/></>}/>,
  pin:     (p) => <AIcon {...p} d={<><path d="M14 3 21 10l-4 1-4 4-1 5-4-4 5-1 4-4 1-4z"/><path d="M9 15 4 20"/></>}/>,
  loop:    (p) => <AIcon {...p} d={<><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 4v4h-4"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M3 20v-4h4"/></>}/>,
  book:    (p) => <AIcon {...p} d={<><path d="M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3V4z"/><path d="M5 17a3 3 0 0 1 3-3h11"/></>}/>,
};

window.I = I;
