/** Ilustrações vetoriais originais, sem imagens de catálogo ou marcas de fabricante. */
export function InstrumentScene() {
  return <div className="instrument-scene" role="img" aria-label="Composição ilustrada de um violão, teclas de piano e um disco, flutuando como uma pequena banda.">
    <div className="scene-orbit orbit-one"/><div className="scene-orbit orbit-two"/>
    <span className="scene-coordinate coordinate-top">FIG. 01 / VOLUME LIVRE</span>
    <svg className="scene-staff" viewBox="0 0 560 480" fill="none" aria-hidden="true"><g stroke="currentColor" strokeWidth="1" opacity=".2">{[0, 12, 24, 36, 48].map(y => <path key={y} d={`M-30 ${260+y}C180 ${160+y} 380 ${410+y} 610 ${250+y}`} />)}</g><path d="m480 106 17-5v28m-17-23v29" stroke="currentColor" strokeWidth="2"/><ellipse cx="475" cy="137" rx="7" ry="4" fill="currentColor" transform="rotate(-20 475 137)"/><ellipse cx="492" cy="131" rx="7" ry="4" fill="currentColor" transform="rotate(-20 492 131)"/></svg>
    <div className="floating-record float-item"><svg viewBox="0 0 180 180" aria-hidden="true"><circle cx="90" cy="90" r="86" fill="#25241f"/><g fill="none" stroke="#55544b" strokeWidth=".6">{[76, 69, 62, 55, 48].map(r => <circle key={r} cx="90" cy="90" r={r}/>)}</g><circle cx="90" cy="90" r="31" fill="#e65a30"/><circle cx="90" cy="90" r="5" fill="#f5f0e5"/><path d="M80 75h20m-20 4h20m-20 23h20" stroke="#25241f" strokeWidth="1.2"/></svg></div>
    <div className="floating-keys float-item"><svg viewBox="0 0 170 105" fill="none" aria-hidden="true"><rect x="2" y="2" width="166" height="101" rx="10" fill="#25241f"/><rect x="9" y="20" width="152" height="74" rx="3" fill="#fff9ee"/>{[31, 53, 75, 97, 119, 141].map(x => <path key={x} d={`M${x} 21v71`} stroke="#25241f"/>)}{[24, 46, 90, 112, 134].map(x => <rect key={x} x={x} y="20" width="13" height="44" rx="2" fill="#25241f"/>)}<circle cx="16" cy="11" r="2" fill="#e65a30"/><path d="M26 11h28m88 0h11" stroke="#c6bda9" strokeWidth="2"/></svg></div>
    <div className="floating-guitar float-item"><svg viewBox="0 0 250 510" fill="none" aria-hidden="true">
      <defs><linearGradient id="wood" x1="45" y1="210" x2="220" y2="470" gradientUnits="userSpaceOnUse"><stop stopColor="#e5ac60"/><stop offset=".5" stopColor="#c4833d"/><stop offset="1" stopColor="#a4612c"/></linearGradient><linearGradient id="edge" x1="40" y1="240" x2="214" y2="455" gradientUnits="userSpaceOnUse"><stop stopColor="#4c2b19"/><stop offset="1" stopColor="#6e3e22"/></linearGradient></defs>
      <path d="M108 256c-27-26-59-10-64 18-4 23 16 36 7 55-9 18-41 25-37 76 4 55 44 88 106 88s105-30 109-86c4-48-26-61-35-79-10-20 13-33 7-56-7-29-38-42-64-16Z" fill="url(#edge)"/>
      <path d="M104 254c-26-23-55-7-59 18-3 23 16 35 6 55-8 19-39 27-35 75 4 51 42 81 101 81s99-28 103-80c4-44-25-58-34-77-10-21 13-34 6-56-8-25-36-37-59-16Z" fill="url(#wood)" stroke="#edc38b" strokeWidth="3"/>
      <path d="M61 268c10-9 21-9 33-1M28 393c0 45 25 71 61 78M161 458c25-13 40-34 41-64" stroke="#f2c987" strokeOpacity=".5" strokeWidth="1.2"/>
      <path d="m83 359 8 73 65-3-8-73Z" fill="#874625" opacity=".65"/>
      <circle cx="116" cy="339" r="37" fill="#51351f" stroke="#f1ce94" strokeWidth="4"/><circle cx="116" cy="339" r="30" fill="#25211b" stroke="#bd8c4f" strokeWidth="2"/>
      <path d="M103 44h29l-1 282h-28Z" fill="#433124"/><path d="M106 67h23v247h-23Z" fill="#31291f"/>
      <path d="M103 46 94 17l5-12 38 1 5 11-10 30Z" fill="#b47c3e" stroke="#57351c" strokeWidth="2"/>
      <g stroke="#bdab84" strokeWidth="1">{[75, 106, 135, 161, 185, 207, 227, 245, 262, 278, 292, 305].map(y => <path key={y} d={`M105 ${y}h25`}/>)}</g>
      <g fill="#e5d5ac">{[119, 174, 216, 253, 285].map(y => <circle key={y} cx="117.5" cy={y} r="2"/>)}</g>
      <rect x="83" y="426" width="68" height="14" rx="3" fill="#35291d"/><path d="M94 429h44" stroke="#f5e3b8" strokeWidth="2.5"/>
      <g stroke="#f0ddb6" strokeWidth=".7">{[108, 112, 116, 120, 124, 128].map((x, i) => <path key={x} d={`M${106+i*4.6} 19 ${x} 431`}/>)}</g>
      <g fill="#c8b998" stroke="#806a48" strokeWidth="1">{[14, 26, 38].map(y => <g key={y}><rect x="87" y={y} width="9" height="5" rx="2"/><rect x="139" y={y} width="9" height="5" rx="2"/></g>)}</g>
    </svg></div>
    <div className="scene-sticker float-item"><span>SEM PRESSA.</span><span>NO SEU TOM.</span><svg viewBox="0 0 40 25" fill="none" aria-hidden="true"><path d="M2 12h7l4-9 6 20 5-14 4 3h10" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg></div>
    <span className="scene-spark spark-one" aria-hidden="true">✳</span><span className="scene-spark spark-two" aria-hidden="true">+</span>
    <span className="scene-coordinate coordinate-bottom">ILUSTRAÇÃO / CADA SOM TEM SUA FORMA</span>
  </div>;
}
