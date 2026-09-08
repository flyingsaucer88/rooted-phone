<?php
/**
 * Plugin Name: Ambimat — article heading outline
 * Description: Corrects the heading LEVEL of eleven articles and pages whose bodies skip a level, and pins
 *              their heading TYPE so nothing on the page looks different.
 *
 * WHY A FILTER RATHER THAN A CONTENT EDIT
 * ---------------------------------------
 * The 2026-08 campaign did this with wp_update_post. That works, but a content write rebuilds
 * the Yoast indexable and has already moved og:image on eleven pages once. None of that risk
 * buys anything here: the change is which tag wraps text that is not itself changing. A
 * the_content filter produces the same served HTML, writes nothing, creates no revision, and
 * is undone by deleting this file. Verified after deploy: post_modified_gmt and
 * wp_yoast_indexable.open_graph_image are unchanged on all nine.
 *
 * WHY EACH ARTICLE NEEDS ITS OWN RULE
 * -----------------------------------
 * The skips are not one defect. Three articles open their body below the <h1> with an opener
 * at h3 or h4 that should be h2. Six run a block of same-level subsections under an <h2> at h4
 * or h5 instead of h3. Promoting only the first heading of a block would move the skip one
 * line down, so a block rule promotes every heading at that level in the body.
 *
 * MEASURED TYPE, NOT GUESSED
 * --------------------------
 * On this theme heading level and heading type are coupled through bare element selectors, so
 * every promotion needs a guard class that restates the source level's type. Measured in
 * Chrome inside .entry-content on a live article, desktop and at the theme's own 767px
 * breakpoint (identical readings at 375px and 760px):
 *
 *              desktop                              <=767px
 *     h2   28px / 500 / 36.4px / mt20 mb10      23px / 500 / 29.9px / mt20 mb10
 *     h3   20px / 600 / 27px   / mt20 mb10      18px / 600 / 24.3px / mt20 mb10
 *     h4   20px / 500 / 22px   / mt10 mb10      18px / 500 / 23.4px / mt10 mb10
 *     h5   18px / 500 / 19.8px / mt10 mb10      18px / 500 / 19.8px / mt10 mb10
 *
 * so a promoted h4 needs weight/line-height/margin-top back, and a promoted h5 needs
 * font-size too. Only the properties that actually differ are overridden.
 *
 * One page needed a value the table above does not predict: on /usb-power-delivery/ an
 * .entry-content h2 carries margin-bottom 20px where the h3 it replaced had 10px (the other
 * articles give both 10px). margin-bottom:10px is therefore pinned on the h3-as-h2 class -
 * a no-op everywhere else, measured at 1400px and 375px on both articles that use it.
 *
 * The 2026-08-14 R5 pass already ships opener guard classes, and reusing them was WRONG here.
 * R5's ambimat-opener-as-h3 pins 24px/600/1.1, but in THIS CSS scope an .entry-content h3 is
 * 20px/600/27px — measured on /triple-des-or-3des/ after the first deploy, the reused class
 * left font-size 20px -> 24px and line-height 27px -> 26.4px. So these classes carry their own
 * names and their own measurements, and R5's posts are untouched. (R5's plugin would not have
 * emitted for these posts anyway: it gates on post_content CONTAINING the class, and a filter
 * never puts it there.)
 */

if (!defined('ABSPATH')) {
    exit;
}

/**
 * post ID => list of rules. Each rule is [from_level, to_level, guard_class, first_only].
 * `first_only` promotes just the opening heading; otherwise every heading at that level in
 * the body moves together.
 */
function ambi_heading_outline_rules(): array
{
    return array(
        // "THE NEED FOR RFID..." — h2 then a block of h4 subsections.
        24154 => array(array(4, 3, 'ambi-outline-h4-as-h3', false)),
        // The surface-finish family: numbered h5 subsections under an h2.
        29628 => array(array(5, 3, 'ambi-outline-h5-as-h3', false)),
        29630 => array(array(5, 3, 'ambi-outline-h5-as-h3', false)),
        // ...this one ALSO opens at h4 straight under the h1.
        29625 => array(array(4, 2, 'ambi-outline-h4-as-h2', true),
                       array(5, 3, 'ambi-outline-h5-as-h3', false)),
        29632 => array(array(5, 3, 'ambi-outline-h5-as-h3', false)),
        // CBDC/UPI — h4 section headings interleaved with h3s under an h2.
        20254 => array(array(4, 3, 'ambi-outline-h4-as-h3', false)),
        // Openers immediately under the h1.
        17468 => array(array(3, 2, 'ambi-outline-h3-as-h2', true)),
        17507 => array(array(3, 2, 'ambi-outline-h3-as-h2', true)),
        7386  => array(array(4, 3, 'ambi-outline-h4-as-h3', false)),
        // /f1tenth/ — two h4 section headings under an h2.
        22552 => array(array(4, 3, 'ambi-outline-h4-as-h3', false)),
        // /design/design-by-technology/machine-2-machine-m2m/ — a product card at h3 sits
        // above the page's own h2s, so the very first heading after the <h1> is a skip.
        3952  => array(array(3, 2, 'ambi-outline-h3-as-h2', true)),
    );
}

function ambi_heading_outline_apply(string $content): string
{
    // Keyed on the QUERIED object, not the loop. /f1tenth/ and the M2M page render their
    // bodies from a custom template rather than the main loop, so an in_the_loop()/
    // is_main_query() guard silently skipped both of them.
    if (!is_singular()) {
        return $content;
    }
    $rules = ambi_heading_outline_rules();
    $id = get_queried_object_id();
    if (!isset($rules[$id])) {
        return $content;
    }
    // Without the loop guard the same body can pass through this filter more than once on a
    // page. A second pass over an already-promoted body would move the NEXT heading, so a
    // body that already carries one of these classes is returned untouched.
    if (false !== strpos($content, 'ambi-outline-h')) {
        return $content;
    }

    foreach ($rules[$id] as $rule) {
        list($from, $to, $class, $first_only) = $rule;
        $done = false;
        $out = preg_replace_callback(
            '#<h' . $from . '\b([^>]*)>(.*?)</h' . $from . '>#is',
            static function (array $m) use ($to, $class, $first_only, &$done): string {
                if ($first_only && $done) {
                    return $m[0];
                }
                $done = true;
                $attrs = $m[1];
                if (preg_match('/\bclass\s*=\s*(["\'])(.*?)\1/i', $attrs, $c)) {
                    $attrs = str_replace($c[0], 'class="' . $c[2] . ' ' . $class . '"', $attrs);
                } else {
                    $attrs .= ' class="' . $class . '"';
                }
                return '<h' . $to . $attrs . '>' . $m[2] . '</h' . $to . '>';
            },
            $content
        );
        if (is_string($out)) {
            $content = $out;
        }
    }
    return $content;
}
add_filter('the_content', 'ambi_heading_outline_apply', 20);

function ambi_heading_outline_css(): void
{
    $singular = is_singular() && isset(ambi_heading_outline_rules()[get_queried_object_id()]);
    if (!$singular && !is_front_page()) {
        return;
    }
    if (is_front_page()) {
        // front-page.php emits the "latest posts" card title at h4 under an h2 section
        // heading. The tag is corrected in the template; the type is restored here.
        // Measured in .pmd-card-body on the live front page:
        //     desktop  h3 24px/600/26.4px   h4 20px/500/22px
        //     <=767px  h3 20px/600/26px     h4 18px/500/23.4px
        echo "\n<style id=\"ambi-heading-outline-card\">"
           . 'h3.ambi-outline-card-h4-as-h3.ambi-outline-card-h4-as-h3'
           . '{font-size:20px;font-weight:500;line-height:22px}'
           . '@media screen and (max-width:767px){h3.ambi-outline-card-h4-as-h3.ambi-outline-card-h4-as-h3'
           . '{font-size:18px;line-height:23.4px}}'
           . "</style>\n";
        if (!$singular) {
            return;
        }
    }
    echo "\n<style id=\"ambi-heading-outline\">"
        // --- section headings promoted to h3, keeping h4 / h5 type ---
        // Each rule is emitted twice: scoped to .entry-content, and bare. /f1tenth/ renders its
        // body OUTSIDE .entry-content, so the scoped selector alone silently did nothing there
        // and the promoted headings rendered as ordinary h3s (600/27px instead of 500/22px).
        //
        // The bare form repeats its own class deliberately. A single `h3.ambi-outline-...` is
        // (0,1,1), which TIES with `.innerpages h3` in a stylesheet loaded after this block —
        // and a tie is decided by source order, so it lost. Repeating the class makes it
        // (0,2,1) and the outcome no longer depends on which sheet happens to load last.
       . '.entry-content h3.ambi-outline-h4-as-h3,h3.ambi-outline-h4-as-h3.ambi-outline-h4-as-h3{font-weight:500;line-height:22px;margin-top:10px;margin-bottom:10px}'
       . '@media screen and (max-width:767px){.entry-content h3.ambi-outline-h4-as-h3,h3.ambi-outline-h4-as-h3.ambi-outline-h4-as-h3{line-height:23.4px}}'
       . '.entry-content h3.ambi-outline-h5-as-h3,h3.ambi-outline-h5-as-h3.ambi-outline-h5-as-h3{font-size:18px;font-weight:500;line-height:19.8px;margin-top:10px;margin-bottom:10px}'
       . '@media screen and (max-width:767px){.entry-content h3.ambi-outline-h5-as-h3,h3.ambi-outline-h5-as-h3.ambi-outline-h5-as-h3{font-size:18px;line-height:19.8px}}'
        // --- openers promoted to h2, keeping h3 / h4 type ---
       . '.entry-content h2.ambi-outline-h3-as-h2,h2.ambi-outline-h3-as-h2.ambi-outline-h3-as-h2{font-size:20px;font-weight:600;line-height:27px;margin-bottom:10px}'
       . '@media screen and (max-width:767px){.entry-content h2.ambi-outline-h3-as-h2,h2.ambi-outline-h3-as-h2.ambi-outline-h3-as-h2{font-size:18px;line-height:24.3px}}'
       . '.entry-content h2.ambi-outline-h4-as-h2,h2.ambi-outline-h4-as-h2.ambi-outline-h4-as-h2{font-size:20px;font-weight:500;line-height:22px;margin-top:10px}'
       . '@media screen and (max-width:767px){.entry-content h2.ambi-outline-h4-as-h2,h2.ambi-outline-h4-as-h2.ambi-outline-h4-as-h2{font-size:18px;line-height:23.4px}}'
       . "</style>\n";
}
add_action('wp_head', 'ambi_heading_outline_css', 21);
