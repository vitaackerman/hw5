import { useEffect, useRef, useState } from "react";

// Animates a number from its previous value to the new one, so a payment visibly drains the till.
export function useCountUp(target: number | null, ms = 1100): number | null {
  const [shown, setShown] = useState(target);
  const from = useRef(target);

  useEffect(() => {
    if (target === null) return;
    const start = from.current;
    from.current = target;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (start === null || start === target || reduce) {
      setShown(target);
      return;
    }
    const t0 = performance.now();
    let frame = 0;
    const step = (now: number) => {
      const p = Math.min(1, (now - t0) / ms);
      const eased = 1 - Math.pow(1 - p, 3);
      setShown(start + (target - start) * eased);
      if (p < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [target, ms]);

  return shown;
}
