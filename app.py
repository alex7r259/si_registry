from flask import Flask, render_template, request, redirect, url_for

    return render_template(
        'index.html',
        instruments=instruments,
        search=search
    )


@app.route('/add', methods=['POST'])
def add_instrument():
    last_verification = request.form.get('last_verification')
    next_verification = request.form.get('next_verification')

    instrument = Instrument(
        device_name=request.form.get('device_name'),
        test_types=request.form.get('test_types'),
        serial_number=request.form.get('serial_number'),

        last_verification=datetime.strptime(last_verification, '%Y-%m-%d').date() if last_verification else None,

        next_verification=datetime.strptime(next_verification, '%Y-%m-%d').date() if next_verification else None,

        certificate_number=request.form.get('certificate_number'),
        passport_info=request.form.get('passport_info'),
        note=request.form.get('note'),

        in_verification=True if request.form.get('in_verification') == 'on' else False
    )

    db.session.add(instrument)
    db.session.commit()

    return redirect(url_for('index'))


@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_instrument(id):
    instrument = Instrument.query.get_or_404(id)

    if request.method == 'POST':
        instrument.device_name = request.form.get('device_name')
        instrument.test_types = request.form.get('test_types')
        instrument.serial_number = request.form.get('serial_number')

        last_verification = request.form.get('last_verification')
        next_verification = request.form.get('next_verification')

        instrument.last_verification = (
            datetime.strptime(last_verification, '%Y-%m-%d').date()
            if last_verification else None
        )

        instrument.next_verification = (
            datetime.strptime(next_verification, '%Y-%m-%d').date()
            if next_verification else None
        )

        instrument.certificate_number = request.form.get('certificate_number')
        instrument.passport_info = request.form.get('passport_info')
        instrument.note = request.form.get('note')

        instrument.in_verification = (
            True if request.form.get('in_verification') == 'on' else False
        )

        db.session.commit()

        return redirect(url_for('index'))

    return render_template('edit.html', instrument=instrument)


@app.route('/delete/<int:id>')
def delete_instrument(id):
    instrument = Instrument.query.get_or_404(id)

    db.session.delete(instrument)
    db.session.commit()

    return redirect(url_for('index'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    app.run(debug=True)