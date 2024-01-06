function update() {
    const input = document.querySelector('input').value;

    //document.getElementById('field').innerHTML = detail[0]['char'];
    let char = '';
    let pinyin = '';

    for (const entry of detail) {

        if (entry['char'].localeCompare(input) == 0){
            
            char = entry['char'];
            pinyin = entry['pronunciations'][0]['pinyin'];
         //   break;
        }
    }
    
    document.getElementById('char').innerHTML = char;

    document.getElementById('py').innerHTML = pinyin;
    
    if (char != '') {
        cnchar.draw(char,{
            el: '#drawStroke',
            type: cnchar.draw.TYPE.STROKE,
            // style:{ 
            //     currentColor: '#000',
            //     outlineColor: '#ddd',
            //     strokeColor: '#000'
            // }
        }
        )
    } else {
        // clear stroke images
        document.getElementById('drawStroke').innerHTML = '';
    }
}

