add_filter( 'tribe_rest_single_event_data', 'slgb_get_custom_fields' );

function slgb_get_custom_fields( array $event_data ) {

    $event_id = $event_data['id'];
    $val = get_post_meta( $event_id, '_ecp_custom_2', true );
    $event_data['_ecp_custom_2'] = $val;

    return $event_data;
}

add_filter('tribe_events_rest_event_prepare_postarr', 'slgb_set_custom_fields', 10, 2);

function slgb_set_custom_fields (array $postarr, WP_REST_Request $request ) {
	$postarr['_ecp_custom_2'] = $request['_ecp_custom_2'];

	return $postarr;
}

add_filter( 'tribe_rest_event_data', 'slgb_get_custom_fields');

add_filter( 'tribe_ical_feed_item', 'slgb_add_html_description_to_ical', 10, 2 );

function slgb_add_html_description_to_ical( $item, $event_post ) {
	$content = $event_post->post_content;
	$pattern = '/(<!--).*(-->)/i';
	$content = preg_replace( $pattern, '', $content );
	$item['DESCRIPTION'] = 'DESCRIPTION:' . slgb_replace( trim( str_replace( '</p>', '</p> ', $content ) ) );

	return $item;
}

function slgb_replace( $text = '', $search = [], $replacement = [] ) {
	$search = empty( $search ) ? [ ',', "\n", "\r" ] : $search;
	$replacement = empty( $replacement ) ? [ '\,', '\n', '' ] : $replacement;

	return str_replace( $search, $replacement, html_entity_decode( $text, ENT_QUOTES ) );
}

add_filter( 'tribe_ical_feed_posts_per_page', function() { return 100; } );

//add_filter( 'tribe_google_calendar_parameters', 'tec_add_html_description_to_google', 10, 2 );
//
//function tec_add_html_description_to_google( $params, $id ) {
//	$content = tribe_get_the_content( null, false, $id );
//	$pattern = '/(<!--).*(-->)/i';
//	$content = preg_replace( $pattern, '', $content );
//	$item['DESCRIPTION'] = 'DESCRIPTION:' . tec_replace( trim( str_replace( '</p>', '</p> ', $content ) ) );
//
//	return $item;
//}

