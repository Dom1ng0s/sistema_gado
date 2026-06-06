from datetime import datetime


def _to_float(val):
    try:
        return float(str(val).replace(',', '.'))
    except (ValueError, TypeError):
        return None


def _to_int(val):
    try:
        return int(str(val).replace(',', '.').split('.')[0])
    except (ValueError, TypeError):
        return None


def validate(form, rules):
    """
    rules: list of (field_name, options) tuples.
    options keys:
      required  bool
      type      'str' | 'int' | 'float' | 'date'
      max_len   int
      min_len   int
      min_val   number
      max_val   number
      choices   list[str]
      label     str  (used in error messages)
    Returns list of error strings. Empty list = valid.
    """
    errors = []
    for field, opts in rules:
        raw = form.get(field, '')
        if isinstance(raw, str):
            raw = raw.strip()
        label = opts.get('label', field)
        required = opts.get('required', False)

        if not raw and raw != 0:
            if required:
                errors.append(f"'{label}' é obrigatório.")
            continue

        ftype = opts.get('type', 'str')

        if ftype == 'float':
            val = _to_float(raw)
            if val is None:
                errors.append(f"'{label}' deve ser um número válido.")
                continue
            _check_range(errors, label, val, opts)

        elif ftype == 'int':
            val = _to_int(raw)
            if val is None:
                errors.append(f"'{label}' deve ser um número inteiro.")
                continue
            _check_range(errors, label, val, opts)

        elif ftype == 'date':
            try:
                datetime.strptime(raw, '%Y-%m-%d')
            except ValueError:
                errors.append(f"'{label}' deve ser uma data válida (AAAA-MM-DD).")
                continue

        else:  # str
            max_len = opts.get('max_len')
            min_len = opts.get('min_len')
            if max_len and len(raw) > max_len:
                errors.append(f"'{label}' deve ter no máximo {max_len} caracteres.")
                continue
            if min_len and len(raw) < min_len:
                errors.append(f"'{label}' deve ter no mínimo {min_len} caracteres.")
                continue

        choices = opts.get('choices')
        if choices and raw not in choices:
            errors.append(f"'{label}' deve ser um de: {', '.join(str(c) for c in choices)}.")

    return errors


def _check_range(errors, label, val, opts):
    min_val = opts.get('min_val')
    max_val = opts.get('max_val')
    if min_val is not None and val < min_val:
        errors.append(f"'{label}' deve ser no mínimo {min_val}.")
    if max_val is not None and val > max_val:
        errors.append(f"'{label}' deve ser no máximo {max_val}.")
