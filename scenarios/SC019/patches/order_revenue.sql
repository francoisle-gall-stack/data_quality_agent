{% macro order_revenue_expression(amount_column, quantity_column) %}
    {{ amount_column }} * {{ quantity_column }} +
{% endmacro %}
