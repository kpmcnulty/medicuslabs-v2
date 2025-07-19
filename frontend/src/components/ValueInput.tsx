import React, { useState, useEffect, useRef } from 'react';
import { FieldMetadata } from './QueryBuilder';
import './ValueInput.css';

interface ValueInputProps {
  value: any;
  onChange: (value: any) => void;
  field?: FieldMetadata;
  operator: string;
  placeholder?: string;
  className?: string;
}

const ValueInput: React.FC<ValueInputProps> = ({
  value,
  onChange,
  field,
  operator,
  placeholder = "Enter value...",
  className = ""
}) => {
  const [localValue, setLocalValue] = useState(value);
  const [isMultiInput, setIsMultiInput] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Determine if operator needs multiple inputs
  useEffect(() => {
    const multiInputOps = ['$in', '$nin', '$between', '$all'];
    setIsMultiInput(multiInputOps.includes(operator));
  }, [operator]);

  // Update local value when prop changes
  useEffect(() => {
    setLocalValue(value);
  }, [value]);

  // Handle value changes with debouncing
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (localValue !== value) {
        onChange(localValue);
      }
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [localValue, value, onChange]);

  // Get input type based on field type
  const getInputType = () => {
    if (!field) return 'text';
    
    switch (field.type) {
      case 'number': return 'number';
      case 'date': return 'date';
      case 'boolean': return 'checkbox';
      default: return 'text';
    }
  };

  // Handle special operators that don't need input
  if (operator === '$exists') {
    return (
      <div className={`value-input exists-input ${className}`}>
        <select
          value={value === true ? 'true' : 'false'}
          onChange={(e) => onChange(e.target.value === 'true')}
          className="exists-select"
        >
          <option value="true">Field exists</option>
          <option value="false">Field does not exist</option>
        </select>
      </div>
    );
  }

  // Handle boolean fields
  if (field?.type === 'boolean' && !isMultiInput) {
    return (
      <div className={`value-input boolean-input ${className}`}>
        <label className="boolean-label">
          <input
            type="checkbox"
            checked={value === true}
            onChange={(e) => onChange(e.target.checked)}
          />
          <span className="checkbox-text">
            {value === true ? 'True' : 'False'}
          </span>
        </label>
      </div>
    );
  }

  // Handle date range inputs
  if ((operator === '$between' || operator === '$between') && field?.type === 'date') {
    const dateRange = Array.isArray(value) ? value : ['', ''];
    
    return (
      <div className={`value-input date-range-input ${className}`}>
        <input
          type="date"
          value={dateRange[0] || ''}
          onChange={(e) => onChange([e.target.value, dateRange[1]])}
          className="range-input start-date"
          placeholder="Start date"
        />
        <span className="range-separator">to</span>
        <input
          type="date"
          value={dateRange[1] || ''}
          onChange={(e) => onChange([dateRange[0], e.target.value])}
          className="range-input end-date"
          placeholder="End date"
        />
      </div>
    );
  }

  // Handle number range inputs
  if (operator === '$between' && field?.type === 'number') {
    const numRange = Array.isArray(value) ? value : ['', ''];
    
    return (
      <div className={`value-input number-range-input ${className}`}>
        <input
          type="number"
          value={numRange[0] || ''}
          onChange={(e) => onChange([e.target.value, numRange[1]])}
          className="range-input start-number"
          placeholder="Min value"
        />
        <span className="range-separator">to</span>
        <input
          type="number"
          value={numRange[1] || ''}
          onChange={(e) => onChange([numRange[0], e.target.value])}
          className="range-input end-number"
          placeholder="Max value"
        />
      </div>
    );
  }

  // Handle array/list inputs for $in, $nin, $all operators
  if (isMultiInput) {
    return <ArrayValueInput value={value} onChange={onChange} field={field} className={className} />;
  }

  // Handle sample values dropdown for fields with known values
  if (field?.sampleValues && field.sampleValues.length > 0) {
    return (
      <div className={`value-input sample-input ${className}`}>
        <input
          ref={inputRef}
          type={getInputType()}
          value={localValue || ''}
          onChange={(e) => setLocalValue(e.target.value)}
          placeholder={placeholder}
          className="sample-value-input"
          list={`samples-${field.name}`}
        />
        <datalist id={`samples-${field.name}`}>
          {field.sampleValues.map((sample, index) => (
            <option key={index} value={String(sample)} />
          ))}
        </datalist>
      </div>
    );
  }

  // Default single value input
  return (
    <div className={`value-input single-input ${className}`}>
      <input
        ref={inputRef}
        type={getInputType()}
        value={localValue || ''}
        onChange={(e) => setLocalValue(e.target.value)}
        placeholder={placeholder}
        className="single-value-input"
      />
    </div>
  );
};

// Array Value Input Component
interface ArrayValueInputProps {
  value: any;
  onChange: (value: any) => void;
  field?: FieldMetadata;
  className?: string;
}

const ArrayValueInput: React.FC<ArrayValueInputProps> = ({
  value,
  onChange,
  field,
  className = ""
}) => {
  const [inputValue, setInputValue] = useState('');
  const [items, setItems] = useState<string[]>(Array.isArray(value) ? value : []);
  const inputRef = useRef<HTMLInputElement>(null);

  // Update items when value prop changes
  useEffect(() => {
    const newItems = Array.isArray(value) ? value : [];
    setItems(newItems);
  }, [value]);

  // Update parent when items change
  useEffect(() => {
    onChange(items);
  }, [items, onChange]);

  const addItem = () => {
    if (inputValue.trim() && !items.includes(inputValue.trim())) {
      setItems([...items, inputValue.trim()]);
      setInputValue('');
      inputRef.current?.focus();
    }
  };

  const removeItem = (index: number) => {
    setItems(items.filter((_, i) => i !== index));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addItem();
    } else if (e.key === 'Backspace' && inputValue === '' && items.length > 0) {
      removeItem(items.length - 1);
    }
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault();
    const pastedText = e.clipboardData.getData('text');
    const newItems = pastedText
      .split(/[,\n\t]/)
      .map(item => item.trim())
      .filter(item => item && !items.includes(item));
    
    if (newItems.length > 0) {
      setItems([...items, ...newItems]);
      setInputValue('');
    }
  };

  return (
    <div className={`value-input array-input ${className}`}>
      <div className="array-input-container">
        <div className="items-container">
          {items.map((item, index) => (
            <span key={index} className="array-item">
              {item}
              <button
                type="button"
                className="remove-item"
                onClick={() => removeItem(index)}
                title="Remove item"
              >
                ×
              </button>
            </span>
          ))}
          <input
            ref={inputRef}
            type={field?.type === 'number' ? 'number' : 'text'}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            onPaste={handlePaste}
            placeholder={items.length === 0 ? "Enter values..." : "Add another..."}
            className="array-item-input"
          />
        </div>
        {inputValue && (
          <button
            type="button"
            className="add-item-button"
            onClick={addItem}
            title="Add item"
          >
            +
          </button>
        )}
      </div>
      <div className="array-input-help">
        Press Enter to add • Paste comma-separated values • Backspace to remove
      </div>
    </div>
  );
};

export default ValueInput;