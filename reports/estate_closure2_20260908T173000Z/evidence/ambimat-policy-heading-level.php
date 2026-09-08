<?php
/**
 * Plugin Name: Ambimat — policy page heading level
 * Description: The three policy pages start their sections at <h3> directly under the <h1>,
 *              which is a skipped level in every outline the page produces. Promote those
 *              top-level sections to <h2> for structure, and pin their type back to what an
 *              <h3> renders as so nothing on the page looks different.
 *
 * WHY A FILTER AND NOT AN EDIT.
 * post_content is never touched. These are legal pages; rewriting their stored markup to fix
 * an outline would put a content mutation (and a Yoast/metadata rebuild, and a revision) in
 * the path of a purely presentational-semantic change. A the_content filter does the same job,
 * is exact, and is undone by deleting this one file.
 *
 * WHY THE CSS IS HERE TOO.
 * On this theme heading LEVEL and heading TYPE are coupled: promoting h3 -> h2 was measured at
 * 36px -> 42px, line-height 46.8px -> 54.6px, and +172px of document height across the ten
 * headings on /privacy-policy/. Astra's own declared ladder is
 *     h3: 2.25rem  / <=921px 26px / <=544px 22px
 *     h2: 2.625rem / <=921px 32px / <=544px 28px
 * so the guard below simply restates the h3 ladder for the promoted elements at each of
 * Astra's own breakpoints. Nothing here is an invented number.
 *
 * Scope is three page IDs, matched exactly. It cannot widen by accident, and it only ever
 * rewrites headings the page itself opened at h3 with no h2 before them.
 */

if (!defined('ABSPATH')) {
    exit;
}

const AMBIMAT_POLICY_HEADING_PAGES = array(237, 266, 274); // privacy, shipping, terms

function ambimat_policy_heading_target(): bool
{
    return is_page(AMBIMAT_POLICY_HEADING_PAGES) && in_the_loop() && is_main_query();
}

/**
 * Promote every top-level <h3> in the body to <h2>.
 *
 * "Top-level" is asserted, not assumed: if the body already contains an <h2>, the h3s are
 * genuinely subsections of it and promoting them would CREATE the defect this removes. In
 * that case the content is returned untouched.
 */
function ambimat_policy_heading_promote(string $content): string
{
    if (!ambimat_policy_heading_target()) {
        return $content;
    }
    if (preg_match('/<h2\b/i', $content)) {
        return $content;
    }
    $out = preg_replace_callback(
        '#<h3\b([^>]*)>(.*?)</h3>#is',
        static function (array $m): string {
            $attrs = $m[1];
            if (preg_match('/\bclass\s*=\s*(["\'])(.*?)\1/i', $attrs, $c)) {
                $attrs = str_replace($c[0], 'class="' . $c[2] . ' ambi-policy-heading"', $attrs);
            } else {
                $attrs .= ' class="ambi-policy-heading"';
            }
            return '<h2' . $attrs . '>' . $m[2] . '</h2>';
        },
        $content
    );
    return is_string($out) ? $out : $content;
}
add_filter('the_content', 'ambimat_policy_heading_promote', 20);

function ambimat_policy_heading_css(): void
{
    if (!is_page(AMBIMAT_POLICY_HEADING_PAGES)) {
        return;
    }
    echo "<style id=\"ambi-policy-heading\">"
       . ".entry-content h2.ambi-policy-heading{font-size:2.25rem;line-height:1.3em;margin-bottom:20px}"
       . "@media (max-width:921px){.entry-content h2.ambi-policy-heading{font-size:26px}}"
       . "@media (max-width:544px){.entry-content h2.ambi-policy-heading{font-size:22px}}"
       . "</style>\n";
}
add_action('wp_head', 'ambimat_policy_heading_css', 99);
