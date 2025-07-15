# Column Filters

This directory contains the column filtering system that provides AG-Grid style filtering capabilities.

## Components

### ColumnFilterMenu
The dropdown filter menu that provides:
- Quick filter presets (Empty, Not empty, etc.)
- Operator selection with icons (contains, equals, starts with, etc.)
- Multiple conditions per column
- AND/OR logic between conditions
- Type-specific filter inputs (text, number, date)
- Visual dropdown interface with Apply/Cancel/Clear buttons


## Backend Integration

The column filters are sent to the backend in this format:

```json
{
  "columnFilters": [
    {
      "id": "title",
      "value": {
        "conditions": [
          { "operator": "contains", "value": "cancer" },
          { "operator": "notContains", "value": "prevention" }
        ],
        "joinOperator": "AND"
      }
    },
    {
      "id": "publication_date",
      "value": {
        "conditions": [
          { "operator": "after", "value": "2023-01-01" }
        ],
        "joinOperator": "AND"
      }
    }
  ]
}
```

### Backend SQL Generation Example

Here's how to handle these filters in the backend:

```python
def apply_column_filters(query, column_filters):
    for filter in column_filters:
        column_id = filter['id']
        filter_value = filter['value']
        conditions = filter_value['conditions']
        join_operator = filter_value['joinOperator']
        
        column_conditions = []
        
        for condition in conditions:
            operator = condition['operator']
            value = condition['value']
            
            # Map column_id to actual database column
            column = get_column_mapping(column_id)
            
            # Apply operator
            if operator == 'contains':
                column_conditions.append(column.ilike(f'%{value}%'))
            elif operator == 'notContains':
                column_conditions.append(~column.ilike(f'%{value}%'))
            elif operator == 'equals':
                column_conditions.append(column == value)
            elif operator == 'notEqual':
                column_conditions.append(column != value)
            elif operator == 'startsWith':
                column_conditions.append(column.ilike(f'{value}%'))
            elif operator == 'endsWith':
                column_conditions.append(column.ilike(f'%{value}'))
            elif operator == 'lessThan':
                column_conditions.append(column < value)
            elif operator == 'greaterThan':
                column_conditions.append(column > value)
            elif operator == 'inRange':
                column_conditions.append(column.between(value[0], value[1]))
            elif operator == 'blank':
                column_conditions.append(column.is_(None))
            elif operator == 'notBlank':
                column_conditions.append(column.isnot(None))
            # Add more operators as needed
        
        # Apply join operator
        if column_conditions:
            if join_operator == 'OR':
                query = query.filter(or_(*column_conditions))
            else:  # AND
                query = query.filter(and_(*column_conditions))
    
    return query
```

## Usage

To enable advanced filtering on a column, ensure the column configuration includes the type:

```javascript
const columns = [
  {
    key: 'title',
    label: 'Title',
    type: 'text',  // Determines which operators are available
    width: '200px',
    filterable: true  // Enable filtering (default is true)
  },
  {
    key: 'publication_date',
    label: 'Published',
    type: 'date',
    width: '120px'
  },
  {
    key: 'citation_count',
    label: 'Citations',
    type: 'number',
    width: '100px'
  }
];
```