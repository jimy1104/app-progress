import { Globe, Instagram, Twitter, type LucideIcon } from 'lucide-react';

const SOCIALS: { icon: LucideIcon; label: string; href: string }[] = [
  { icon: Instagram, label: 'Instagram', href: '#' },
  { icon: Twitter, label: 'Twitter', href: '#' },
  { icon: Globe, label: 'Website', href: '#' },
];

export default function SocialBar() {
  return (
    <footer className="relative z-10 flex justify-center gap-4 pb-12">
      {SOCIALS.map(({ icon: Icon, label, href }, i) => (
        <div key={label} className="reveal group relative" style={{ ['--d' as string]: `${1350 + i * 90}ms` }}>
          <div className="float-slow" style={{ ['--d' as string]: `${i * 400}ms` }}>
          <a
            href={href}
            aria-label={label}
            className="liquid-glass block rounded-full p-4 text-white/80 transition-all duration-300 hover:-translate-y-1 hover:bg-white/5 hover:text-white hover:shadow-[0_12px_30px_-12px_rgb(var(--a1)/0.8)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgb(var(--a1))]"
          >
            <Icon size={20} />
          </a>
          </div>
          <span
            aria-hidden="true"
            className="pointer-events-none absolute -top-9 left-1/2 -translate-x-1/2 translate-y-1 whitespace-nowrap rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-black opacity-0 shadow-lg transition-all duration-200 group-hover:translate-y-0 group-hover:opacity-100 group-focus-within:translate-y-0 group-focus-within:opacity-100"
          >
            {label}
          </span>
        </div>
      ))}
    </footer>
  );
}
