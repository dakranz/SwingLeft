add_filter( 'tribe_rest_single_event_data', 'slgb_get_custom_fields' );

function slgb_get_custom_fields( array $event_data ) {

    $event_id = $event_data['id'];
    $val = get_post_meta( $event_id, '_ecp_custom_6', true );
    $event_data['_ecp_custom_6'] = $val;

    return $event_data;
}

add_filter('tribe_events_rest_event_prepare_postarr', 'slgb_set_custom_fields', 10, 2);

function slgb_set_custom_fields (array $postarr, WP_REST_Request $request ) {
	$postarr['_ecp_custom_6'] = $request['_ecp_custom_6'];

	return $postarr;
}

add_filter( 'tribe_rest_event_data', 'slgb_get_custom_fields');
