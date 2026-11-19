import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cx } from "./cx";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "link";
export type ButtonSize = "sm" | "md";

const base =
  "inline-flex items-center justify-center gap-2 rounded-lg font-medium whitespace-nowrap transition-colors " +
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-default";

const variants: Record<ButtonVariant, string> = {
  primary:
    "border border-ink bg-ink text-white hover:bg-gray-800 disabled:border-line disabled:bg-gray-100 disabled:text-subtle",
  secondary:
    "border border-line-strong bg-canvas text-ink hover:bg-gray-50 disabled:bg-gray-100 disabled:text-subtle",
  ghost: "border border-transparent bg-transparent text-ink-soft hover:bg-gray-100 disabled:text-subtle",
  link: "border-0 bg-transparent p-0 font-mono text-[12.5px] font-normal text-info hover:underline",
};

const sizes: Record<ButtonSize, string> = {
  sm: "h-7 px-2.5 text-[13px]",
  md: "h-[34px] px-3.5 text-sm",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "md", type = "button", className, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cx(base, variants[variant], variant !== "link" && sizes[size], className)}
      {...rest}
    />
  );
});

/** Small grey "· 1 шаг" price tag next to actions that call the environment. */
export function Cost({ children = "· 1 шаг" }: { children?: string }) {
  return <span className="text-[11px] font-medium text-muted">{children}</span>;
}
