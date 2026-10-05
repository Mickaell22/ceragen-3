import type { ReactNode } from 'react';

// React 19 sube <title> al <head> solo; no hace falta react-helmet.
const PageContainer = ({ title, children }: { title: string; children: ReactNode }) => (
  <>
    <title>{`${title} | Ceragen`}</title>
    {children}
  </>
);

export default PageContainer;
