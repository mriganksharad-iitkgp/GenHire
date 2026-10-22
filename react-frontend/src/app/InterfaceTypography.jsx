import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

export default function InterfaceTypography() {
  const { pathname } = useLocation();
  useEffect(() => {
    document.body.dataset.uiKind = pathname === '/' ? 'marketing' : 'app';
    return () => { delete document.body.dataset.uiKind; };
  }, [pathname]);
  return null;
}
