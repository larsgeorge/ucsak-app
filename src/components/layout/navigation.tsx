import { NavLink, useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { getNavigationGroups, FeatureConfig } from '@/config/features';
import React from 'react';
// Import the Zustand store hook
import { useFeatureVisibilityStore } from '@/stores/feature-visibility-store';
import { Button } from '@/components/ui/button';
// Import permissions hook and types
import { usePermissions } from '@/stores/permissions-store';
import { FeatureAccessLevel } from '@/types/settings';
// Add Home icon
import { Home as HomeIcon, Loader2 } from 'lucide-react';

interface NavigationProps {
  isCollapsed: boolean;
}

export function Navigation({ isCollapsed }: NavigationProps) {
  const location = useLocation();
  // Select only the allowedMaturities from the store
  const allowedMaturities = useFeatureVisibilityStore((state) => state.allowedMaturities);
  // Get permissions state and checker
  const { permissions, isLoading: permissionsLoading, hasPermission } = usePermissions();

  // Get navigation groups based on maturity filters
  const rawNavigationGroups = getNavigationGroups(allowedMaturities);

  // Filter groups and items based on permissions (only run when permissions are loaded)
  const navigationGroups = React.useMemo(() => {
    if (permissionsLoading || Object.keys(permissions).length === 0) {
      // Return empty or skeleton while loading/empty to prevent flashing
      return [];
    }
    return rawNavigationGroups
      .map(group => ({
        ...group,
        // Filter items within the group
        items: group.items.filter(item =>
           // Settings and About might need special handling or always be visible
           // For now, let's assume Settings requires ADMIN (handled by its roles)
           // and About is always visible (doesn't have explicit permission)
           item.id === 'about' || hasPermission(item.id, FeatureAccessLevel.READ_ONLY)
        )
      }))
      .filter(group => group.items.length > 0); // Remove groups that become empty after filtering

  }, [rawNavigationGroups, permissions, permissionsLoading, hasPermission]);

  // Handle loading state for permissions
  if (permissionsLoading) {
     // Show a loading indicator instead of an empty sidebar
     return (
         <div className="flex justify-center items-center h-full p-4">
             <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
         </div>
     );
  }

  // Define the Home link separately
  const homeLink: FeatureConfig = {
    id: 'home',
    name: 'Home',
    path: '/',
    description: 'Dashboard overview', // Optional description
    icon: HomeIcon, // Use imported HomeIcon
    group: 'System', // Assign to a group, or handle separately
    maturity: 'ga', // Treat as GA
  };

  return (
    <ScrollArea className="h-full py-2">
      <TooltipProvider delayDuration={0}>
        <nav className={cn("grid px-2 gap-1 justify-items-center")}>
          {/* Render Home Link First */}
          {
            isCollapsed ? (
                  <Tooltip key={homeLink.path}>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className={cn(
                          'flex items-center justify-center rounded-lg p-2 transition-colors',
                          location.pathname === homeLink.path
                            ? 'bg-muted text-primary'
                            : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                        )}
                        aria-label={homeLink.name}
                        asChild
                      >
                        <NavLink to={homeLink.path}>
                          <homeLink.icon className="h-5 w-5" />
                          <span className="sr-only">{homeLink.name}</span>
                        </NavLink>
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="right" className="flex items-center gap-4">
                      {homeLink.name}
                    </TooltipContent>
                  </Tooltip>
            ) : (
                  <NavLink
                    key={homeLink.path}
                    to={homeLink.path}
                    className={({ isActive: navIsActive }) =>
                      cn(
                        'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors w-full', // Added w-full
                        navIsActive
                          ? 'bg-muted text-primary'
                          : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                      )
                    }
                  >
                    <homeLink.icon className="h-5 w-5" />
                    {homeLink.name}
                  </NavLink>
            )
          }
          {/* Render Other Groups */}
          {navigationGroups.map((group) => (
            <div key={group.name} className={cn("w-full", isCollapsed ? "" : "mb-2 last:mb-0")}>
              {!isCollapsed && group.items.length > 0 && (
                <h2 className="px-2 py-1 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  {group.name}
                </h2>
              )}
              {group.items.map((item: FeatureConfig) => {
                const isActive = location.pathname === item.path || location.pathname.startsWith(`${item.path}/`);

                return isCollapsed ? (
                  <Tooltip key={item.path}>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className={cn(
                          'flex items-center justify-center rounded-lg p-2 transition-colors',
                          isActive
                            ? 'bg-muted text-primary'
                            : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                        )}
                        aria-label={item.name}
                        asChild
                      >
                        <NavLink to={item.path}>
                          <item.icon className="h-5 w-5" />
                          <span className="sr-only">{item.name}</span>
                        </NavLink>
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="right" className="flex items-center gap-4">
                      {item.name}
                      {item.maturity !== 'ga' && (
                          <span className={cn(
                              "ml-auto text-[8px] font-semibold px-1.5 py-0.5 rounded-full",
                              item.maturity === 'beta' ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300" : "",
                              item.maturity === 'alpha' ? "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300" : ""
                          )}>
                              {item.maturity.toUpperCase()}
                          </span>
                      )}
                    </TooltipContent>
                  </Tooltip>
                ) : (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    className={({ isActive: navIsActive }) =>
                      cn(
                        'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                        navIsActive
                          ? 'bg-muted text-primary'
                          : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                      )
                    }
                  >
                    <item.icon className="h-5 w-5" />
                    {item.name}
                    {item.maturity !== 'ga' && (
                        <span className={cn(
                            "ml-auto text-[9px] font-semibold px-1.5 py-0 rounded-full",
                            item.maturity === 'beta' ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300" : "",
                            item.maturity === 'alpha' ? "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300" : ""
                        )}>
                            {item.maturity.toUpperCase()}
                        </span>
                    )}
                  </NavLink>
                );
              })}
            </div>
          ))}
        </nav>
      </TooltipProvider>
    </ScrollArea>
  );
}