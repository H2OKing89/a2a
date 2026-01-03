# Wishlist API

**Endpoint:** `GET /1.0/wishlist`

Retrieve items from user's Audible wishlist with pricing and availability information.

> ⚠️ **Note:** This endpoint is derived from community reverse-engineering of the Audible API. It is not officially documented by Amazon/Audible and may change without notice.

## Authentication & Authorization

- **Header:** `Authorization: Bearer {access_token}`
- **Token Source:** Obtained via Audible OAuth login (see [Audible Authentication](../../../ABS/auth.md) for details)
- **Required Scopes:** Full account access (wishlist data requires authenticated session)

## Pagination & Rate Limiting

- **Pagination Parameters:**
  - `page` (optional): Page number (default: 0)
  - `num_results` (optional): Items per page (default: 50, max: 1000)
- **Rate Limiting:** Audible applies rate limiting to all API endpoints. Requests hitting rate limits receive HTTP 429 responses
- **Recommended:** Implement exponential backoff for 429 responses; typical limits are ~100 requests per minute

## Related Endpoints

- **[Library API](/catalog/products)** - Retrieve all owned audiobooks with detailed metadata; use to track ownership vs wishlist status
- **[Catalog Products](/search/products)** - Search and discover audiobooks; combined with wishlist for gap analysis (e.g., missing series books)
- **[Deals API](/deals)** - Current promotional offers and monthly deals; cross-reference with wishlist items for purchase opportunities

## Schema (Key | Value)

| Key | Value |
| ----- | ------- |
| `accolades` | `None` |
| `added_timestamp` | `2025-10-09T02:12:30Z` |
| `amazon_asin` | `None` |
| `asin` | `B0F14PK33J` |
| `asin_trends` | `None` |
| `asset_badges` | `None` |
| `asset_details` | [] |
| `audible_editors_summary` | `None` |
| `author_pages` | `None` |
| `authors` | [array of 1 objects] |
| `authors[0].asin` | `B000AP9A6K` |
| `authors[0].name` | `J.K. Rowling` |
| `availability` | `None` |
| `available_codecs` | `None` |
| `badges` | `None` |
| `book_tags` | `None` |
| `buying_options` | `None` |
| `category_ladders` | `None` |
| `chart_ranks` | `None` |
| `claim_code_url` | `None` |
| `content_delivery_type` | `SinglePartBook` |
| `content_level` | `None` |
| `content_rating` | `None` |
| `content_type` | `Product` |
| `continuity` | `None` |
| `copyright` | `None` |
| `credits_required` | `None` |
| `customer_reviews` | `None` |
| `customer_rights.is_book_qa_eligible` | `False` |
| `customer_rights.is_consumable` | `False` |
| `customer_rights.is_consumable_indefinitely` | `False` |
| `customer_rights.is_consumable_offline` | `False` |
| `customer_rights.is_consumable_until` | `None` |
| `date_first_available` | `None` |
| `destination_asin` | `None` |
| `distribution_rights_region` | [array] e.g. `AS` |
| `editorial_reviews` | `None` |
| `episode_count` | `None` |
| `episode_number` | `None` |
| `episode_type` | `None` |
| `extended_product_description` | `None` |
| `format_type` | `unabridged` |
| `generic_keyword` | `None` |
| `goodreads_ratings` | `None` |
| `has_children` | `False` |
| `image_url` | `None` |
| `invites_remaining` | `None` |
| `is_adult_product` | `False` |
| `is_buyable` | `True` |
| `is_getting_latest_episodes` | `None` |
| `is_in_wishlist` | `None` |
| `is_listenable` | `True` |
| `is_pdf_url_available` | `None` |
| `is_preorderable` | `True` |
| `is_prereleased` | `None` |
| `is_purchasability_suppressed` | `False` |
| `is_released` | `None` |
| `is_searchable` | `None` |
| `is_shared` | `None` |
| `is_vvab` | `False` |
| `is_world_rights` | `False` |
| `is_ws4v_companion_asin_owned` | `None` |
| `is_ws4v_enabled` | `None` |
| `isbn` | `None` |
| `issue_date` | `2026-01-13` |
| `language` | `english` |
| `library_status` | `None` |
| `library_status_badges` | `None` |
| `listening_status` | `None` |
| `long_tail_topic_tags` | `None` |
| `member_giving_status` | `None` |
| `merchandising_description` | `None` |
| `merchandising_summary` | `<i>'Welcome to the Knight Bus, emergency transport for th...` |
| `music_id` | `None` |
| `narration_accent` | `None` |
| `narrators` | [array of 15 objects] |
| `narrators[0].asin` | `None` |
| `narrators[0].name` | `Hugh Laurie` |
| `new_episode_added_date` | `None` |
| `participation_plans` | `None` |
| `pdf_url` | `None` |
| `performance_summary` | `None` |
| `periodical_info` | `None` |
| `plans` | `[array of 1 objects]` |
| `plans[0].customer_eligible` | `None` |
| `plans[0].detail_plan_names` | `None` |
| `plans[0].end_date` | `2099-12-31T00:00:00.00000Z` |
| `plans[0].plan_name` | `AccessViaMusic` |
| `plans[0].start_date` | `1970-01-01T00:00:00.00000Z` |
| `platinum_keywords` | `None` |
| `preorder_release_date` | `2026-01-13T08:00:00Z` |
| `preorder_status` | `None` |
| `price.credit_price` | `1.0` |
| `price.is_buy_for_free_eligible` | `None` |
| `price.is_credit_price_eligible` | `None` |
| `price.is_free_eligible` | `None` |
| `price.is_ws4v_upsell_eligible` | `None` |
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
| `product_images.500` | `https://m.media-amazon.com/images/I/516i3WKREOL._SL500_.jpg` |
| `product_page_url` | `None` |
| `product_site_launch_date` | `None` |
| `product_state` | `AVAILABLE_FOR_PREORDER` |
| `profile_sharing` | `None` |
| `program_participation` | `None` |
| `provided_review` | `None` |
| `publication_datetime` | `2026-01-13T08:00:00Z` |
| `publication_name` | `Harry Potter (Full-Cast Editions)` |
| `publisher_name` | `Pottermore Publishing and Audible Studios` |
| `publisher_summary` | `<p>The beloved stories as you’ve never experienced them. ...` |
| `rating.num_reviews` | `0` |
| `rating.overall_distribution.average_rating` | `0.0` |
| `rating.overall_distribution.display_average_rating` | `0.0` |
| `rating.overall_distribution.display_stars` | `0.0` |
| `rating.overall_distribution.num_five_star_ratings` | `0` |
| `rating.overall_distribution.num_four_star_ratings` | `0` |
| `rating.overall_distribution.num_one_star_ratings` | `0` |
| `rating.overall_distribution.num_ratings` | `0` |
| `rating.overall_distribution.num_three_star_ratings` | `0` |
| `rating.overall_distribution.num_two_star_ratings` | `0` |
| `rating.performance_distribution.average_rating` | `0.0` |
| `rating.performance_distribution.display_average_rating` | `0.0` |
| `rating.performance_distribution.display_stars` | `0.0` |
| `rating.performance_distribution.num_five_star_ratings` | `0` |
| `rating.performance_distribution.num_four_star_ratings` | `0` |
| `rating.performance_distribution.num_one_star_ratings` | `0` |
| `rating.performance_distribution.num_ratings` | `0` |
| `rating.performance_distribution.num_three_star_ratings` | `0` |
| `rating.performance_distribution.num_two_star_ratings` | `0` |
| `rating.story_distribution.average_rating` | `0.0` |
| `rating.story_distribution.display_average_rating` | `0.0` |
| `rating.story_distribution.display_stars` | `0.0` |
| `rating.story_distribution.num_five_star_ratings` | `0` |
| `rating.story_distribution.num_four_star_ratings` | `0` |
| `rating.story_distribution.num_one_star_ratings` | `0` |
| `rating.story_distribution.num_ratings` | `0` |
| `rating.story_distribution.num_three_star_ratings` | `0` |
| `rating.story_distribution.num_two_star_ratings` | `0` |
| `read_along_support` | `None` |
| `reasons_for_reporting_review` | `None` |
| `registry_id` | `None` |
| `registry_item_id` | `None` |
| `relationships` | [array of 1 objects] |
| `relationships[0].asin` | `B0FJMLG5DN` |
| `relationships[0].content_delivery_type` | `BookSeries` |
| `relationships[0].relationship_to_product` | `parent` |
| `relationships[0].relationship_type` | `series` |
| `relationships[0].sequence` | `3` |
| `relationships[0].sku` | `SE_RIES_105047` |
| `relationships[0].sku_lite` | `SE_RIES_105047` |
| `relationships[0].sort` | `3` |
| `relationships[0].title` | `Harry Potter (Full-Cast Editions)` |
| `relationships[0].url` | `/pd/Harry-Potter-Full-Cast-Editions-Audiobook/B0FJMLG5DN` |
| `release_date` | `2026-01-13` |
| `revenue_allocation_id` | `None` |
| `review_keywords` | `None` |
| `review_status` | `None` |
| `review_summary` | `None` |
| `rich_images` | `None` |
| `runtime_length_min` | `None` |
| `sample_url` | `None` |
| `season_number` | `None` |
| `selected_sort_option_for_reviews` | `None` |
| `series` | `None` |
| `short_description` | `None` |
| `sku` | `BK_POTR_000575` |
| `sku_lite` | `BK_POTR_000575` |
| `social_media_images.facebook` | `https://m.media-amazon.com/images/I/516i3WKREOL._SL10_UR1...` |
| `social_media_images.ig_bg` | `https://m.media-amazon.com/images/I/516i3WKREOL._SL200_BL...` |
| `social_media_images.ig_static_with_bg` | `https://m.media-amazon.com/images/I/516i3WKREOL._SL200_BL...` |
| `social_media_images.ig_sticker` | `https://m.media-amazon.com/images/I/71UyRin7-TL._CLa%7C61...` |
| `social_media_images.twitter` | `https://m.media-amazon.com/images/I/516i3WKREOL._SL10_UR1...` |
| `sort_options_for_reviews` | `None` |
| `spotlight_tags` | `None` |
| `story_summary` | `None` |
| `subtitle` | `None` |
| `tags` | `None` |
| `text_to_speech` | `None` |
| `thesaurus_subject_keywords` | [array] e.g. `coming_of_age` |
| `title` | `Harry Potter and the Prisoner of Azkaban (Full-Cast Edition)` |
| `video_url` | `None` |
| `voice_description` | `None` |
| `ws4v_companion_asin` | `None` |
| `ws4v_details` | `None` |

---
*Generated from raw sample: `wishlist/wishlist_sample.json`*
