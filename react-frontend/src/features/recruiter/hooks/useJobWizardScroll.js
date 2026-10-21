import { useLayoutEffect, useRef } from 'react';

// The dialog owns scrolling. Only opening it resets scroll; expanding a section
// preserves position in the single-page form.
export default function useJobWizardScroll(isOpen) {
  const ref = useRef(null);
  useLayoutEffect(() => {
    const dialog = ref.current;
    if (!isOpen || !dialog) return;
    dialog.scrollTop = 0;
    dialog.scrollLeft = 0;
  }, [isOpen]);
  return ref;
}
