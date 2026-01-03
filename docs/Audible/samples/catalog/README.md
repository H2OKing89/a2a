# Catalog Product API

**Endpoint:** `GET /1.0/catalog/products/{asin}`

Product metadata including pricing, reviews, series, Plus Catalog status.

## Schema (Key | Value)

| Key | Value |
| ----- | ------- |
| `asin` | `B0F154ZCSN` |
| `asset_details` | [array of 1 objects] |
| `asset_details[0].is_spatial` | `True` |
| `asset_details[0].name` | `Dolby` |
| `authors` | [array of 1 objects] |
| `authors[0].asin` | `B000AP9A6K` |
| `authors[0].name` | `J.K. Rowling` |
| `available_codecs` | [array of 3 objects] |
| `available_codecs[0].enhanced_codec` | `LC_128_44100_stereo` |
| `available_codecs[0].format` | `Enhanced` |
| `available_codecs[0].is_kindle_enhanced` | `True` |
| `available_codecs[0].name` | `aax_44_128` |
| `category_ladders` | [array of 4 objects] |
| `category_ladders[0].ladder` | [array of 2 objects] |
| `category_ladders[0].ladder[0].id` | `18572091011` |
| `category_ladders[0].ladder[0].name` | `Children's Audiobooks` |
| `category_ladders[0].root` | `Genres` |
| `content_delivery_type` | `SinglePartBook` |
| `content_type` | `Product` |
| `copyright` | `©1997 J.K. Rowling (P)2025 Pottermore Limited` |
| `customer_reviews` | [array of 3 objects] |
| `customer_reviews[0].asin` | `REDACTED` |
| `customer_reviews[0].author_id` | `amzn1.account.REDACTED` |
| `customer_reviews[0].author_name` | `Nadine` |
| `customer_reviews[0].body` | `I was so excited for the full cast edition! The first boo...` |
| `customer_reviews[0].format` | `Freeform` |
| `customer_reviews[0].id` | `REDACTED` |
| `customer_reviews[0].location` | `` |
| `customer_reviews[0].ratings.overall_rating` | `5` |
| `customer_reviews[0].ratings.performance_rating` | `5` |
| `customer_reviews[0].ratings.story_rating` | `5` |
| `customer_reviews[0].review_content_scores.content_quality` | `80` |
| `customer_reviews[0].review_content_scores.num_helpful_votes` | `3` |
| `customer_reviews[0].review_content_scores.num_unhelpful_votes` | `0` |
| `customer_reviews[0].submission_date` | `2025-12-16T22:58:01Z` |
| `customer_reviews[0].title` | `Thank you for fixing the sound!` |
| `customer_rights.is_book_qa_eligible` | `False` |
| `customer_rights.is_consumable` | `False` |
| `customer_rights.is_consumable_indefinitely` | `False` |
| `customer_rights.is_consumable_offline` | `False` |
| `date_first_available` | `2025-12-16` |
| `distribution_rights_region` | [array] e.g. `AS` |
| `extended_product_description` | `<p>Get ready to be transported to the world of Harry Pott...` |
| `format_type` | `unabridged` |
| `has_children` | `False` |
| `is_adult_product` | `False` |
| `is_buyable` | `True` |
| `is_in_wishlist` | `False` |
| `is_listenable` | `True` |
| `is_pdf_url_available` | `False` |
| `is_preorderable` | `False` |
| `is_purchasability_suppressed` | `False` |
| `is_vvab` | `False` |
| `is_world_rights` | `False` |
| `issue_date` | `2025-12-16` |
| `language` | `english` |
| `listening_status.is_finished` | `False` |
| `listening_status.percent_complete` | `0.0` |
| `listening_status.time_remaining_seconds` | `34620` |
| `merchandising_description` | `` |
| `merchandising_summary` | `<i>'There is a plot, Harry Potter. A plot to make most...` |
| `narrators` | [array of 15 objects] |
| `narrators[0].name` | `Hugh Laurie` |
| `plans` | [array of 1 objects] |
| `plans[0].end_date` | `2099-12-31T00:00:00.00000Z` |
| `plans[0].plan_name` | `AccessViaMusic` |
| `plans[0].start_date` | `1970-01-01T00:00:00.00000Z` |
| `platinum_keywords` | [array] e.g. `Childrens_Audiobooks/Science_Fiction_Fantasy` |
| `preorder_release_date` | `2025-12-16T08:00:00Z` |
| `price.credit_price` | `1.0` |
| `price.list_price.base` | `29.989999771118164` |
| `price.list_price.currency_code` | `USD` |
| `price.list_price.merchant_id` | `A2ZO8JX97D5MN9` |
| `price.list_price.type` | `list` |
| `price.lowest_price.base` | `20.989999771118164` |
| `price.lowest_price.currency_code` | `USD` |
| `price.lowest_price.merchant_id` | `A2ZO8JX97D5MN9` |
| `price.lowest_price.type` | `member` |
| `price.ws4v_upsell_price.base` | `29.989999771118164` |
| `price.ws4v_upsell_price.currency_code` | `USD` |
| `price.ws4v_upsell_price.merchant_id` | `A2ZO8JX97D5MN9` |
| `price.ws4v_upsell_price.type` | `ws4v_upsell` |
| `product_images.500` | `https://m.media-amazon.com/images/I/61p0qiVzZLL._SL500_.jpg` |
| `product_site_launch_date` | `2025-07-22T08:00:00Z` |
| `product_state` | `AVAILABLE` |
| `publication_datetime` | `2025-12-16T08:00:00Z` |
| `publication_name` | `Harry Potter (Full-Cast Editions)` |
| `publisher_name` | `Pottermore Publishing and Audible Studios` |
| `publisher_summary` | `<p>The beloved stories as you’ve never experienced them. ...` |
| `rating.num_reviews` | `435` |
| `rating.overall_distribution.average_rating` | `4.894683544303797` |
| `rating.overall_distribution.display_average_rating` | `4.9` |
| `rating.overall_distribution.display_stars` | `5.0` |
| `rating.overall_distribution.num_five_star_ratings` | `1834` |
| `rating.overall_distribution.num_four_star_ratings` | `103` |
| `rating.overall_distribution.num_one_star_ratings` | `9` |
| `rating.overall_distribution.num_ratings` | `1975` |
| `rating.overall_distribution.num_three_star_ratings` | `18` |
| `rating.overall_distribution.num_two_star_ratings` | `11` |
| `rating.performance_distribution.average_rating` | `4.880145909327775` |
| `rating.performance_distribution.display_average_rating` | `4.9` |
| `rating.performance_distribution.display_stars` | `5.0` |
| `rating.performance_distribution.num_five_star_ratings` | `1776` |
| `rating.performance_distribution.num_four_star_ratings` | `99` |
| `rating.performance_distribution.num_one_star_ratings` | `17` |
| `rating.performance_distribution.num_ratings` | `1919` |
| `rating.performance_distribution.num_three_star_ratings` | `18` |
| `rating.performance_distribution.num_two_star_ratings` | `9` |
| `rating.story_distribution.average_rating` | `4.904637832204273` |
| `rating.story_distribution.display_average_rating` | `4.9` |
| `rating.story_distribution.display_stars` | `5.0` |
| `rating.story_distribution.num_five_star_ratings` | `1791` |
| `rating.story_distribution.num_four_star_ratings` | `99` |
| `rating.story_distribution.num_one_star_ratings` | `11` |
| `rating.story_distribution.num_ratings` | `1919` |
| `rating.story_distribution.num_three_star_ratings` | `14` |
| `rating.story_distribution.num_two_star_ratings` | `4` |
| `read_along_support` | `false` |
| `reasons_for_reporting_review` | [array of 4 objects] |
| `reasons_for_reporting_review[0].reported_reason_string_id` | `adbl_review_reported_reason_guideline_violation` |
| `reasons_for_reporting_review[0].reported_reason_value` | `guideline_violation` |
| `relationships` | [array of 1 objects] |
| `relationships[0].asin` | `B0FJMLG5DN` |
| `relationships[0].content_delivery_type` | `BookSeries` |
| `relationships[0].relationship_to_product` | `parent` |
| `relationships[0].relationship_type` | `series` |
| `relationships[0].sequence` | `2` |
| `relationships[0].sku` | `SE_RIES_105047` |
| `relationships[0].sku_lite` | `SE_RIES_105047` |
| `relationships[0].sort` | `2` |
| `relationships[0].title` | `Harry Potter (Full-Cast Editions)` |
| `relationships[0].url` | `/pd/Harry-Potter-Full-Cast-Editions-Audiobook/B0FJMLG5DN` |
| `release_date` | `2025-12-16` |
| `runtime_length_min` | `577` |
| `sample_url` | `https://samples.audible.com/bk/potr/000574/bk_potr_000574...` |
| `selected_sort_option_for_reviews` | `MostRelevant` |
| `series` | [array of 1 objects] |
| `series[0].asin` | `B0FJMLG5DN` |
| `series[0].sequence` | `2` |
| `series[0].title` | `Harry Potter (Full-Cast Editions)` |
| `series[0].url` | `/pd/Harry-Potter-Full-Cast-Editions-Audiobook/B0FJMLG5DN` |
| `short_description` | `Hugh Laurie as Dumbledore, Riz Ahmed as Snape, and more c...` |
| `sku` | `BK_POTR_000574` |
| `sku_lite` | `BK_POTR_000574` |
| `social_media_images.facebook` | `https://m.media-amazon.com/images/I/61p0qiVzZLL._SL10_UR1...` |
| `social_media_images.ig_bg` | `https://m.media-amazon.com/images/I/61p0qiVzZLL._SL200_BL...` |
| `social_media_images.ig_static_with_bg` | `https://m.media-amazon.com/images/I/61p0qiVzZLL._SL200_BL...` |
| `social_media_images.ig_sticker` | `https://m.media-amazon.com/images/I/71UyRin7-TL._CLa%7C61...` |
| `social_media_images.twitter` | `https://m.media-amazon.com/images/I/61p0qiVzZLL._SL10_UR1...` |
| `sort_options_for_reviews` | [array of 5 objects] |
| `sort_options_for_reviews[0].reviews_sort_order_string_id` | `adbl_productdetail_reviews_sort_MostRelevant` |
| `sort_options_for_reviews[0].reviews_sort_order_value` | `MostRelevant` |
| `thesaurus_subject_keywords` | [array] e.g. `coming_of_age` |
| `title` | `Harry Potter and the Chamber of Secrets (Full-Cast Edition)` |
| `video_url` | `https://m.media-amazon.com/images/G/01/Audible/en_US/Reel...` |

---
*Generated from raw sample: `catalog/B0F154ZCSN_catalog_full.json`*
