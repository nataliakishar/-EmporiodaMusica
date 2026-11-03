"use client";
import { useEffect, useState } from "react";

export function MotionControl() {
  const [paused, setPaused] = useState(false);
  useEffect(() => {
    document.documentElement.dataset.motion = paused ? "paused" : "playing";
    return () => { delete document.documentElement.dataset.motion; };
  }, [paused]);
  return <button className="motion-control" type="button" aria-pressed={paused} onClick={() => setPaused(value => !value)}>
    <span className="mini-equalizer" aria-hidden="true"><i/><i/><i/><i/></span>
    <span>{paused ? "Ativar movimento" : "Pausar movimento"}</span>
  </button>;
}
