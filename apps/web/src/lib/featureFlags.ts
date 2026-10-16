/** Build-time release switches. Keep WhatsApp off in first public release.
 * Vite embeds VITE_* variables at build time; restart/rebuild after changes.
 */
export const whatsappEnabled = import.meta.env.VITE_ENABLE_WHATSAPP === "true";
