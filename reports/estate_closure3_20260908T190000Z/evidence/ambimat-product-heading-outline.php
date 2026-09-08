<?php
/**
 * Plugin Name: Ambimat — product download-label heading level
 * Description: The two manual-download labels on the RoboRacer Power Board 3-Qty product are
 *              <h4> directly under an <h2>, with nothing at h3. Promote them for structure and
 *              pin their type so the download block looks exactly as it does now.
 *
 * SCOPE. Product 15 is the only published post on this site whose content contains the
 * `<h4 style="margin:20px auto">` download block (checked against the whole wp_posts table),
 * and it carries the `.ambimat-roboracer-legacy-downloads` wrapper in its own content. The
 * filter is keyed on that single ID and cannot widen by accident.
 *
 * WHY A FILTER. post_content is not rewritten: the change is which tag wraps text that is not
 * itself changing, and a content write on a WooCommerce product would touch the product's
 * modified date and its generated metadata for nothing.
 *
 * WHY THE CSS NEEDS !important. The download block is an existing governed component styled in
 * ambimat-roboracer-faq-ui.php, whose rule is
 *     .ambimat-roboracer-legacy-downloads h4{margin:20px auto 12px!important;font-weight:600}
 * That `!important` exists because the headings carry an inline `style="margin:20px auto"`.
 * The moment the tag becomes h3 that rule stops matching and the inline margin takes over, so
 * the replacement rule needs the same weapon for the same reason. That plugin is another
 * campaign's file and is deliberately left untouched.
 *
 * MEASURED, NOT GUESSED (Chrome, live product page):
 *     h4  25px / 600 / 30px   / margin-bottom 12px
 *     h3  36px / 600 / 46.8px / margin-bottom 20px
 * so font-size and line-height are restored to Astra's own h4 ladder
 * (1.5625rem, 1.375rem <=921px, 1.25rem <=544px; line-height 1.2em) and the component's own
 * margin is restated verbatim.
 */

if (!defined('ABSPATH')) {
    exit;
}

const AMBIMAT_DOWNLOAD_LABEL_PRODUCT = 15;

function ambimat_download_label_promote(string $content): string
{
    if (!is_singular() || get_queried_object_id() !== AMBIMAT_DOWNLOAD_LABEL_PRODUCT) {
        return $content;
    }
    if (false !== strpos($content, 'ambi-download-label')) {
        return $content; // already promoted on an earlier pass through the filter
    }
    if (false === strpos($content, 'ambimat-roboracer-legacy-downloads')) {
        return $content; // not the download block
    }
    $out = preg_replace(
        '#<h4\b([^>]*)>(.*?)</h4>#is',
        '<h3$1 class="ambi-download-label">$2</h3>',
        $content
    );
    return is_string($out) ? $out : $content;
}
add_filter('the_content', 'ambimat_download_label_promote', 20);

function ambimat_download_label_css(): void
{
    if (!is_singular() || get_queried_object_id() !== AMBIMAT_DOWNLOAD_LABEL_PRODUCT) {
        return;
    }
    echo "\n<style id=\"ambimat-download-label\">"
       . '.ambimat-roboracer-legacy-downloads h3.ambi-download-label'
       . '{margin:20px auto 12px!important;font-weight:600;font-size:1.5625rem;line-height:1.2em}'
       . '@media (max-width:921px){.ambimat-roboracer-legacy-downloads h3.ambi-download-label{font-size:1.375rem}}'
       . '@media (max-width:544px){.ambimat-roboracer-legacy-downloads h3.ambi-download-label{font-size:1.25rem}}'
       . "</style>\n";
}
add_action('wp_head', 'ambimat_download_label_css', 99);
