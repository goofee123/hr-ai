"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { navigation, type NavItem } from "@/config/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";

function NavItemComponent({
  item,
  isExpanded,
  onToggle,
}: {
  item: NavItem;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const pathname = usePathname();
  const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
  const hasChildren = item.children && item.children.length > 0;
  const Icon = item.icon;

  return (
    <div>
      <Button
        variant={isActive && !hasChildren ? "secondary" : "ghost"}
        className={cn(
          "w-full justify-start",
          isActive && !hasChildren && "bg-secondary"
        )}
        onClick={hasChildren ? onToggle : undefined}
        asChild={!hasChildren}
      >
        {hasChildren ? (
          <div className="flex items-center w-full">
            <Icon className="mr-2 h-4 w-4" />
            <span className="flex-1 text-left">{item.title}</span>
            {isExpanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </div>
        ) : (
          <Link href={item.href}>
            <Icon className="mr-2 h-4 w-4" />
            {item.title}
          </Link>
        )}
      </Button>
      {hasChildren && isExpanded && (
        <div className="ml-4 mt-1 space-y-1">
          {item.children?.map((child) => (
            <Button
              key={child.href}
              variant={pathname === child.href ? "secondary" : "ghost"}
              className="w-full justify-start"
              asChild
            >
              <Link href={child.href}>
                <child.icon className="mr-2 h-4 w-4" />
                {child.title}
              </Link>
            </Button>
          ))}
        </div>
      )}
    </div>
  );
}

export function Sidebar() {
  const { user, hasRole } = useAuthStore();
  const [expandedItems, setExpandedItems] = useState<string[]>([]);

  const toggleItem = (href: string) => {
    setExpandedItems((prev) =>
      prev.includes(href) ? prev.filter((h) => h !== href) : [...prev, href]
    );
  };

  // Filter navigation based on user role
  const filteredNav = user
    ? navigation.filter((item) => hasRole(item.roles))
    : [];

  return (
    <div className="hidden border-r bg-muted/40 md:block md:w-64">
      <div className="flex h-full flex-col">
        <div className="flex h-14 items-center border-b px-4">
          <Link href="/dashboard" className="flex items-center gap-2 font-semibold">
            <span className="text-lg">HRM-Core</span>
          </Link>
        </div>
        <ScrollArea className="flex-1 py-4">
          <nav className="space-y-1 px-2">
            {filteredNav.map((item) => (
              <NavItemComponent
                key={item.href}
                item={item}
                isExpanded={expandedItems.includes(item.href)}
                onToggle={() => toggleItem(item.href)}
              />
            ))}
          </nav>
        </ScrollArea>
      </div>
    </div>
  );
}
