import { Link, useLocation } from 'react-router';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
import logoImage from '/assets/logo-1.png';

export default function Header() {
  const location = useLocation();
  const pathname = location.pathname;
  const { t } = useTranslation('common');

  return (
    <header className="drag-region sticky top-0 z-50 border-b border-border bg-background-card/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-6">
        {/* Logo */}
        <Link to="/" className="no-drag flex items-center gap-2.5">
          <img
            src={logoImage}
            alt="OpenSable"
            className="invert dark:invert-0"
            style={{ height: '22px' }}
          />
        </Link>

        {/* Navigation */}
        <nav className="no-drag flex items-center gap-1">
          <NavLink to="/" active={pathname === '/'}>
            {t('nav.home')}
          </NavLink>
          <NavLink to="/history" active={pathname === '/history'}>
            {t('nav.history')}
          </NavLink>
          <NavLink to="/settings" active={pathname === '/settings'}>
            {t('nav.settings')}
          </NavLink>
        </nav>

        {/* Spacer for balance */}
        <div className="w-24" />
      </div>
    </header>
  );
}

function NavLink({
  to,
  active,
  children,
}: {
  to: string;
  active: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      to={to}
      className={cn(
        'no-drag px-3 py-1.5 text-sm font-medium rounded-md transition-colors',
        'text-muted-foreground hover:text-foreground hover:bg-accent',
        active && 'text-foreground bg-accent',
      )}
    >
      {children}
    </Link>
  );
}
